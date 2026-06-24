"""Walk-in reception assignment (leads spec §4.2d). Three company-configured
policies: Open Floor, Team Turn (head assigns), Full Rotation. The lead is
always created with source Walk-in and the how-did-you-know prompt captured."""
from __future__ import annotations

from django.db import transaction

from apps.policies.constants import PolicyCode
from apps.policies.services import PolicyResolver

from ..constants import SourceCode
from ..models import WalkInQueueEntry
from .lead_creation_service import LeadCreationService

OPEN_FLOOR = "OPEN_FLOOR"
TEAM_TURN = "TEAM_TURN"
FULL_ROTATION = "FULL_ROTATION"


class WalkInService:
    @staticmethod
    @transaction.atomic
    def register(*, company, name, phone, receptionist=None, how_did_you_know="",
                 actor=None, request_meta=None, **extra):
        policy = PolicyResolver.option_code(
            company, PolicyCode.WALKIN_RECEPTION_POLICY, default=OPEN_FLOOR
        )
        meta = {"how_did_you_know": how_did_you_know, "walkin_policy": policy}
        # Walk-in distribution is manual/policy-driven, never auto Round Robin.
        lead = LeadCreationService.create(
            company=company, source_code=SourceCode.WALK_IN, name=name, phone=phone,
            actor=actor, request_meta=request_meta, auto_distribute=False,
            metadata=meta, **extra,
        )
        entry = WalkInQueueEntry.objects.create(
            lead=lead, receptionist=receptionist, selected_policy_code=policy
        )
        WalkInService._apply_policy(policy, lead, entry, actor, request_meta)
        lead.refresh_from_db()
        return lead

    @staticmethod
    def _apply_policy(policy, lead, entry, actor, request_meta):
        from apps.distribution.services import (
            DistributionEngine,
            ManualDistributionEscalation,
        )

        if policy == FULL_ROTATION:
            # Single company-wide By-Turn rotation across all salesmen.
            DistributionEngine.distribute(
                lead=lead, actor=actor, request_meta=request_meta, strategy_code="BY_TURN"
            )
        elif policy == TEAM_TURN:
            # Next team in rotation; that team's head picks the salesman.
            team = WalkInService._next_team(lead.company)
            if team is None:
                ManualDistributionEscalation.notify(
                    company=lead.company, lead=lead, actor=actor
                )
            else:
                from apps.distribution.services import ManualAssignmentService

                ManualAssignmentService.assign_to_team(
                    lead_id=lead.id, team=team, actor=actor,
                    reason="Walk-in team turn", request_meta=request_meta,
                )
        else:  # OPEN_FLOOR: any available salesman; receptionist flags it.
            ManualDistributionEscalation.notify(
                company=lead.company, lead=lead, actor=actor
            )

    @staticmethod
    def _next_team(company):
        from apps.accounts.models import Team
        from apps.distribution.models import RotationPointer
        from apps.distribution.selectors import eligible_pool
        from apps.leads.constants import ScopeMode

        teams = list(
            Team.objects.filter(company=company, is_active=True).order_by("order_index")
        )
        if not teams:
            return None
        pointer, _ = RotationPointer.objects.select_for_update().get_or_create(
            company=company, pointer_code="WALKIN_TEAM_TURN", scope="GLOBAL",
            defaults={"current_index": 0},
        )
        for _ in range(len(teams)):
            idx = pointer.current_index % len(teams)
            team = teams[idx]
            pointer.current_index = (idx + 1) % len(teams)
            pointer.save(update_fields=["current_index", "updated_at"])

            # Check if this team has available salesmen
            pool = eligible_pool(
                company=company, team=team, scope_mode=ScopeMode.TEAM_THEN_SALESMAN
            )
            if pool:
                return team
        return None
