"""Stage transitions + universal rotation rule (docs §9.1, §9.2). On SLA rotation
the visible stage resets to Fresh and the Fresh SLA restarts while all history is
preserved. Views never set stages directly."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.notifications.constants import NotificationCode
from apps.notifications.services import NotificationService

from ..constants import ActiveStatus, SLAStatus, StageCode
from ..models import Lead, LeadStageDefinition, LeadStageHistory
from .sla_service import SLAService


class LeadStageService:
    @staticmethod
    @transaction.atomic
    def change_stage(*, lead_id, to_stage_code: str, actor=None, reason: str = "",
                     request_meta=None, frozen_days: int = 0, scheduled_time=None) -> Lead:
        lead = Lead.objects.select_for_update().select_related(
            "company", "assigned_salesman", "current_stage"
        ).get(id=lead_id)
        to_stage = LeadStageDefinition.objects.get(code=to_stage_code)
        from_stage = lead.current_stage
        sla_before = lead.sla_deadline

        lead.current_stage = to_stage
        deadline = SLAService.calculate_deadline(
            lead.company, stage_code=to_stage_code, origin=lead.origin,
            source_code=lead.source.code if lead.source else None, frozen_days=frozen_days,
            scheduled_time=scheduled_time
        )
        # Not Interested is terminal -> lead becomes Inactive, no SLA (docs §9.1).
        skip_sla = False
        if lead.source and lead.source.code == "SELF_GENERATED" and lead.assigned_salesman_id == lead.created_by_id:
            creator = lead.created_by
            if creator and creator.team_memberships.filter(team__company=lead.company).exists():
                from apps.policies.constants import PolicyCode
                from apps.policies.services import PolicyResolver
                sg_policy = PolicyResolver.option_code(
                    lead.company, PolicyCode.SELF_GENERATED_SALESMAN_POLICY, default="KEEP_WITH_OWNER"
                )
                if sg_policy == "KEEP_WITH_OWNER":
                    skip_sla = True

        if to_stage.is_terminal or to_stage_code == StageCode.NOT_INTERESTED:
            lead.active_status = ActiveStatus.INACTIVE
            lead.sla_deadline = None
            lead.sla_instances.filter(status=SLAStatus.ACTIVE).update(
                status=SLAStatus.CANCELLED
            )
        elif skip_sla:
            lead.sla_deadline = None
            lead.sla_instances.filter(status=SLAStatus.ACTIVE).update(
                status=SLAStatus.CANCELLED
            )
        else:
            lead.sla_deadline = deadline
            SLAService.open_instance(lead=lead, stage=to_stage, deadline=deadline)
        lead.last_activity_at = timezone.now()
        lead.save(update_fields=[
            "current_stage", "active_status", "sla_deadline",
            "last_activity_at", "updated_at",
        ])

        LeadStageHistory.objects.create(
            lead=lead, from_stage=from_stage, to_stage=to_stage, actor=actor,
            reason=reason, sla_before=sla_before, sla_after=lead.sla_deadline,
        )
        AuditService.log(
            action=AuditAction.STAGE_CHANGE, instance=lead, actor=actor,
            company=lead.company, module="leads", request_meta=request_meta,
            before={"stage": getattr(from_stage, "code", None)},
            after={"stage": to_stage_code}, reason=reason,
        )
        if to_stage_code not in (StageCode.FOLLOW_UP, StageCode.MEETING, StageCode.NOT_REACHED, StageCode.INTERESTED, StageCode.NOT_INTERESTED, StageCode.FROZEN):
            NotificationService.create(
                company=lead.company, recipient=lead.assigned_salesman,
                code=NotificationCode.STAGE_CHANGED, title=f"Lead moved to {to_stage.name}",
                related_type="Lead", related_id=lead.pk,
            )

        if to_stage_code == StageCode.NOT_REACHED:
            from apps.policies.constants import PolicyCode
            from apps.policies.services import PolicyResolver
            from .reminder_service import ReminderService
            from .sla_service import _duration_to_timedelta

            mode = PolicyResolver.option_code(
                lead.company, PolicyCode.NOT_REACHED_REMINDER_MODE, default="AUTOMATIC"
            )
            if mode == "AUTOMATIC":
                interval_val = PolicyResolver.param(
                    lead.company, PolicyCode.NOT_REACHED_REMINDER_MODE, "interval", default=None
                )
                if interval_val is not None:
                    delta = _duration_to_timedelta(interval_val)
                else:
                    stage_sla_val = PolicyResolver.value(
                        lead.company, f"{PolicyCode.STAGE_SLA}.not_reached", default={"hours": 2}
                    )
                    delta = _duration_to_timedelta(stage_sla_val)

                due_at = timezone.now() + delta
                if lead.assigned_salesman:
                    ReminderService.create(
                        company=lead.company, user=lead.assigned_salesman, due_at=due_at,
                        reminder_type="STAGE_NOT_REACHED", lead=lead, related_type="Lead",
                        related_id=lead.pk
                    )
            elif mode == "MANUAL" and scheduled_time:
                if lead.assigned_salesman:
                    ReminderService.create(
                        company=lead.company, user=lead.assigned_salesman, due_at=scheduled_time,
                        reminder_type="STAGE_NOT_REACHED", lead=lead, related_type="Lead",
                        related_id=lead.pk
                    )

        return lead

    @staticmethod
    @transaction.atomic
    def freeze(*, lead_id, days: int, actor=None, reason: str = "",
               request_meta=None) -> Lead:
        """Frozen stage with a lead-defined call-back period (leads spec §9.1).
        Moves to Frozen via change_stage (audit + history + SLA) and schedules a
        return reminder `days` from now for the assigned salesman."""
        from datetime import timedelta

        from .reminder_service import ReminderService
        from .sales_action_policy_service import (
            enforce_action_limit, enforce_max_duration,
        )

        locked = Lead.objects.select_related("company", "assigned_salesman").get(id=lead_id)
        enforce_action_limit(lead=locked, salesman=locked.assigned_salesman,
                             actor=actor, action="freeze")
        enforce_max_duration(company=locked.company, actor=actor, action="freeze",
                             days=days)

        lead = LeadStageService.change_stage(
            lead_id=lead_id, to_stage_code=StageCode.FROZEN, actor=actor,
            reason=reason, request_meta=request_meta, frozen_days=days,
        )
        if lead.assigned_salesman_id and days > 0:
            ReminderService.create(
                company=lead.company, user=lead.assigned_salesman,
                due_at=timezone.now() + timedelta(days=days),
                reminder_type="FROZEN_RETURN", lead=lead, related_type="Lead",
                related_id=lead.pk,
            )
        return lead

    @staticmethod
    def reset_to_fresh(*, lead: Lead, actor=None, reason="SLA rotation") -> None:
        """Universal rotation rule (docs §9.2): reset visible stage to Fresh and
        restart the Fresh SLA. History is preserved by the caller's new
        assignment/stage records. Call inside an open transaction with a locked
        lead row."""
        fresh = LeadStageDefinition.objects.get(code=StageCode.FRESH)
        from_stage = lead.current_stage
        sla_before = lead.sla_deadline
        deadline = SLAService.calculate_deadline(
            lead.company, stage_code=StageCode.FRESH, origin=lead.origin,
            source_code=lead.source.code if lead.source else None
        )
        lead.current_stage = fresh
        lead.sla_deadline = deadline
        lead.last_activity_at = timezone.now()
        lead.save(update_fields=[
            "current_stage", "sla_deadline", "last_activity_at", "updated_at"
        ])
        SLAService.open_instance(lead=lead, stage=fresh, deadline=deadline)
        LeadStageHistory.objects.create(
            lead=lead, from_stage=from_stage, to_stage=fresh, actor=actor,
            reason=reason, sla_before=sla_before, sla_after=deadline,
        )
