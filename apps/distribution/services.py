"""Distribution services (docs §8.3, §8.4, §16.2). DistributionEngine resolves
the policy-selected strategy + scope mode and assigns through one shared,
locked, audited routine. Manual paths and retry/team escalation reuse it."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ValidationError
from apps.leads.constants import (
    AssignmentMethod,
    ScopeMode,
    SLAExpiryMethod,
    StageCode,
)
from apps.leads.models import Lead, LeadAssignmentHistory
from apps.notifications.constants import NotificationCode
from apps.notifications.services import NotificationService
from apps.policies.constants import PolicyCode
from apps.policies.services import PolicyResolver

from . import registry  # noqa: F401  (registers built-in strategies on import)
from .models import DistributionCandidateSnapshot, DistributionRun
from .registry import StrategyRegistry
from .selectors import eligible_pool


def _assign(*, lead: Lead, team, salesman, method: str, strategy_code: str = "",
            actor=None, reason: str = "", request_meta=None) -> Lead:
    """Shared assignment routine (docs §16.2): lock, mutate, reset to Fresh,
    open SLA, write history + audit, notify on commit. Idempotent-safe to call
    from manual, auto, SLA-rotation, retry and escalation paths."""
    from apps.leads.services.lead_stage_service import LeadStageService

    lead = Lead.objects.select_for_update().select_related(
        "company", "assigned_team", "assigned_salesman"
    ).get(id=lead.id)
    from_team, from_salesman = lead.assigned_team, lead.assigned_salesman

    lead.assigned_team = team
    lead.assigned_salesman = salesman
    lead.save(update_fields=["assigned_team", "assigned_salesman", "updated_at"])

    # Universal rotation rule: new owner starts Fresh with full SLA (docs §9.2).
    LeadStageService.reset_to_fresh(lead=lead, actor=actor, reason=reason or "Assigned")

    LeadAssignmentHistory.objects.create(
        lead=lead, from_team=from_team, to_team=team,
        from_salesman=from_salesman, to_salesman=salesman,
        assignment_method=method, strategy_code=strategy_code,
        reason=reason, actor=actor,
    )
    # Assignment is already captured in LeadAssignmentHistory (Lead history); no audit write.
    code = (
        NotificationCode.LEAD_REASSIGNED_SLA
        if method in (AssignmentMethod.SLA_ROTATION, AssignmentMethod.ESCALATION)
        else NotificationCode.LEAD_ASSIGNED
    )
    if salesman:
        NotificationService.create_for_users(
            company=lead.company, recipients=[salesman],
            code=code, title="Lead assigned", related_type="Lead", related_id=lead.pk,
        )
    return lead


class ManualAssignmentService:
    @staticmethod
    @transaction.atomic
    def assign_to_salesman(*, lead_id, salesman, team=None, actor=None, reason="",
                           request_meta=None) -> Lead:
        lead = Lead.objects.select_related("company", "assigned_team", "assigned_salesman").get(id=lead_id)
        return _assign(
            lead=lead, team=team or lead.assigned_team, salesman=salesman,
            method=AssignmentMethod.MANUAL, actor=actor, reason=reason,
            request_meta=request_meta,
        )

    @staticmethod
    @transaction.atomic
    def assign_to_team(*, lead_id, team, actor=None, reason="", request_meta=None) -> Lead:
        """Assign to a team; Sales Head later picks the salesman (docs §8.3,
        scope mode TEAM_HEAD_DECIDES)."""
        lead = Lead.objects.select_related("company", "assigned_team", "assigned_salesman").get(id=lead_id)
        lead = _assign(
            lead=lead, team=team, salesman=None, method=AssignmentMethod.MANUAL,
            actor=actor, reason=reason, request_meta=request_meta,
        )
        NotificationService.create_for_users(
            company=lead.company, recipients=[team.sales_head],
            code=NotificationCode.MANUAL_DISTRIBUTION_REQUIRED,
            title="Pick salesman for assigned team lead",
            related_type="Lead", related_id=lead.pk,
        )
        return lead


class DistributionEngine:
    @staticmethod
    @transaction.atomic
    def distribute(*, lead, actor=None, request_meta=None, team=None, strategy_code=None) -> Lead:
        company = lead.company
        method = strategy_code or PolicyResolver.strategy_code(
            company, PolicyCode.DEFAULT_AUTO_DISTRIBUTION_METHOD, default="ROUND_ROBIN"
        )
        scope_mode = PolicyResolver.option_code(
            company, PolicyCode.DISTRIBUTION_SCOPE_MODE,
            default=ScopeMode.ALL_SALESMEN,
        )

        print(f"\n==================================================")
        print(f"[DISTRIBUTION START] Lead: {lead.id} | Name: '{lead.name}' | Company: {company.id}")
        print(f"   Origin: {lead.origin} | Language: {lead.language} | Stage: {getattr(lead.current_stage, 'code', None)}")
        print(f"   Current Assigned Salesman: {lead.assigned_salesman} (ID: {lead.assigned_salesman_id})")
        print(f"   Requested Team Filter: {team} | Strategy Code Override: {strategy_code}")
        print(f"   Resolved Strategy: {method} | Scope Mode: {scope_mode}")
        print(f"==================================================")

        run = DistributionRun.objects.create(
            company=company, lead=lead, method_code=method, scope_mode=scope_mode,
            language=lead.language, actor=actor,
        )
        pool = eligible_pool(
            company=company, language=lead.language, scope_mode=scope_mode, team=team
        )
        print(f"[POOL ELIGIBLE] Initial Pool Size: {len(pool)}")
        print(f"   Candidates: {[(m.user.email, m.team.name) for m in pool]}")

        if lead.assigned_salesman_id:
            pool = [m for m in pool if m.user_id != lead.assigned_salesman_id] or pool
            print(f"[POOL FILTERED] Current salesman excluded. Final Pool Size: {len(pool)}")
            print(f"   Final Candidates: {[(m.user.email, m.team.name) for m in pool]}")

        if not pool:
            print(f"[DISTRIBUTION FAILED] Pool is empty! Escalate to manual.")
            print(f"==================================================\n")
            run.status = "NO_CANDIDATE"
            run.error = "Empty eligible pool after language/scope filter"
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error", "finished_at"])
            ManualDistributionEscalation.notify(company=company, lead=lead, actor=actor)
            return lead

        strategy = StrategyRegistry.get(method)
        from .interfaces import DistributionContext

        decision = strategy.select_candidate(
            company=company, lead=lead, eligible_pool=pool,
            context=DistributionContext(company=company, scope_mode=scope_mode,
                                        language=lead.language, actor=actor),
        )
        print(f"[STRATEGY SELECTION] Strategy '{method}' evaluated.")
        print(f"   Decision - Salesman: {decision.salesman} (ID: {getattr(decision.salesman, 'id', None)}) | Team: {decision.team}")
        print(f"   Reason: '{decision.reason}'")

        DistributionEngine._record_candidates(run, pool, decision)

        if decision.salesman is None and decision.team is None:
            print(f"[DISTRIBUTION FAILED] Strategy returned no candidate! Escalate to manual.")
            print(f"==================================================\n")
            run.status = "NO_CANDIDATE"
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "finished_at"])
            ManualDistributionEscalation.notify(company=company, lead=lead, actor=actor)
            return lead

        # Scope mode 2: engine picks team, Sales Head decides salesman (§8.4).
        if scope_mode == ScopeMode.TEAM_HEAD_DECIDES:
            print(f"[ASSIGNMENT] Scope Mode: TEAM_HEAD_DECIDES -> Assigning to team: {decision.team}")
            lead = ManualAssignmentService.assign_to_team(
                lead_id=lead.id, team=decision.team, actor=actor,
                reason="Auto: team selected, head decides", request_meta=request_meta,
            )
        else:
            print(f"[ASSIGNMENT] Assigning to salesman: {decision.salesman} | Team: {decision.team}")
            lead = _assign(
                lead=lead, team=decision.team, salesman=decision.salesman,
                method=AssignmentMethod.AUTO, strategy_code=method, actor=actor,
                reason=decision.reason, request_meta=request_meta,
            )
        print(f"[DISTRIBUTION DONE] Lead {lead.id} assignment completed successfully.")
        print(f"==================================================\n")

        run.status = "DONE"
        run.selected_team = decision.team
        run.selected_salesman = decision.salesman
        run.finished_at = timezone.now()
        run.save(update_fields=[
            "status", "selected_team", "selected_salesman", "finished_at"
        ])
        return lead

    @staticmethod
    def _record_candidates(run, pool, decision):
        from .selectors import batch_candidate_loads

        chosen = getattr(decision.salesman, "pk", None)
        loads = batch_candidate_loads([m.user for m in pool], run.company)
        rows = []
        for member in pool:
            active, last = loads.get(member.user_id, (0, None))
            rows.append(DistributionCandidateSnapshot(
                run=run, candidate_type="SALESMAN", candidate_user=member.user,
                active_lead_count=active, last_received_at=last,
                is_eligible=True,
                rejection_reason="" if member.user_id == chosen else "Not selected",
            ))
        DistributionCandidateSnapshot.objects.bulk_create(rows)


class RetryEscalationService:
    """RETRY_TEAM_ESCALATION expiry method (docs §8.3): cycle salesmen in the
    current team for n attempts, then escalate to the next team."""

    @staticmethod
    @transaction.atomic
    def handle_expiry(*, lead, actor=None, request_meta=None) -> Lead:
        company = lead.company
        n = int(PolicyResolver.param(
            company, PolicyCode.RETRY_ATTEMPTS_PER_TEAM, "attempts", default=3
        ) or 3)
        from .models import LeadRetryAttempt

        attempts = LeadRetryAttempt.objects.filter(
            lead=lead, team=lead.assigned_team_id
        ).count()
        if attempts < n:
            return RetryEscalationService._retry_within_team(
                lead, attempts + 1, actor, request_meta
            )
        return RetryEscalationService._escalate_next_team(lead, actor, request_meta)

    @staticmethod
    def _retry_within_team(lead, attempt_number, actor, request_meta):
        pool = eligible_pool(
            company=lead.company, language=lead.language,
            scope_mode=ScopeMode.TEAM_THEN_SALESMAN, team=lead.assigned_team,
        )
        pool = [m for m in pool if m.user_id != lead.assigned_salesman_id] or pool
        if not pool:
            ManualDistributionEscalation.notify(
                company=lead.company, lead=lead, actor=actor
            )
            return lead
        member = pool[(attempt_number - 1) % len(pool)]
        from .models import LeadRetryAttempt

        LeadRetryAttempt.objects.create(
            lead=lead, team=member.team, salesman=member.user,
            attempt_number=attempt_number,
        )
        return _assign(
            lead=lead, team=member.team, salesman=member.user,
            method=AssignmentMethod.RETRY, actor=actor,
            reason=f"Retry attempt {attempt_number}", request_meta=request_meta,
        )

    @staticmethod
    def _escalate_next_team(lead, actor, request_meta):
        from apps.leads.constants import Origin

        if lead.origin == Origin.BROKER:
            ManualDistributionEscalation.notify(
                company=lead.company, lead=lead, actor=actor
            )
            return lead

        from apps.accounts.models import Team

        next_team = (
            Team.objects.filter(
                company=lead.company, is_active=True,
                order_index__gt=getattr(lead.assigned_team, "order_index", -1),
            )
            .order_by("order_index")
            .first()
        )
        if next_team is None:
            ManualDistributionEscalation.notify(
                company=lead.company, lead=lead, actor=actor
            )
            return lead
        return DistributionEngine.distribute(
            lead=lead, actor=actor, request_meta=request_meta, team=next_team
        )


class ManualDistributionEscalation:
    """Call Me Again / broker / empty-pool cases route to manual distributors
    (docs §8.1, §12.3 MANUAL_DISTRIBUTION_REQUIRED)."""

    @staticmethod
    def notify(*, company, lead, actor=None) -> None:
        from apps.distribution.selectors import manual_distributors

        NotificationService.create_for_users(
            company=company, recipients=manual_distributors(company),
            code=NotificationCode.MANUAL_DISTRIBUTION_REQUIRED,
            title="Lead needs manual distribution",
            related_type="Lead", related_id=lead.pk,
        )


def resolve_expiry_method(company) -> str:
    return PolicyResolver.option_code(
        company, PolicyCode.SLA_EXPIRY_METHOD, default=SLAExpiryMethod.ROUND_ROBIN
    )


class SLAExpiryService:
    """Handles one expired SLA instance idempotently (docs §12.2). Marks the
    breach, then applies the configured expiry method. Caller holds the row lock
    via locks.expired_sla_batch."""

    @staticmethod
    def process_instance(sla_instance, *, task_id="", actor=None) -> bool:
        from apps.leads.constants import SLAStatus, Origin
        from apps.leads.models import SLABreachEvent

        # Idempotency: only an still-active instance gets processed (§12.2).
        if sla_instance.status != SLAStatus.ACTIVE:
            return False
        lead = sla_instance.lead
        sla_instance.status = SLAStatus.BREACHED
        sla_instance.breached_at = timezone.now()
        sla_instance.save(update_fields=["status", "breached_at"])

        method = resolve_expiry_method(lead.company)
        if lead.origin == Origin.BROKER and method == SLAExpiryMethod.ROUND_ROBIN:
            method = SLAExpiryMethod.MANUAL

        SLABreachEvent.objects.create(
            sla_instance=sla_instance, lead=lead, breach_type="SLA_EXPIRY",
            handled_by_task_id=task_id, action_taken=method,
        )
        # SLA expiry is recorded in SLABreachEvent (Lead history); no audit write.
        # Task 10b: no more "SLA breached" notification. Instead clear the (now
        # ex-)owner's lead-assigned, follow-up, meeting and freeze notifications
        # for this lead — done before reassignment so the new owner's stay intact.
        NotificationService.clear_for_lead_breach(
            recipient=lead.assigned_salesman, lead=lead,
        )

        if method == SLAExpiryMethod.ROUND_ROBIN:
            DistributionEngine.distribute(lead=lead, actor=actor)
        elif method == SLAExpiryMethod.BY_TURN:
            DistributionEngine.distribute(lead=lead, actor=actor, strategy_code="BY_TURN")
        elif method == SLAExpiryMethod.RETRY_TEAM_ESCALATION:
            RetryEscalationService.handle_expiry(lead=lead, actor=actor)
        else:  # MANUAL (broker leads default here, docs §7.2)
            ManualDistributionEscalation.notify(
                company=lead.company, lead=lead, actor=actor
            )
        return True
