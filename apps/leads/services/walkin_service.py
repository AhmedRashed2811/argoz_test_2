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

ROT_FULL = "WALKIN_FULL_ROTATION"
ROT_TEAM = "WALKIN_TEAM_TURN"


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
            WalkInService.advance_pointer(
                lead.company, ROT_FULL, len(WalkInService.available_members(lead.company))
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

    # ── Interactive rotation (matches the receptionist UI; docs §4.2d) ──
    @staticmethod
    def available_members(company):
        """Available salesmen in a stable company-wide order (the By-Turn order)."""
        from apps.accounts.models import TeamMember

        return list(
            TeamMember.objects.select_related("user", "team").filter(
                team__company=company, team__is_active=True, is_available=True,
                user__is_active=True, user__profile__availability_status="AVAILABLE",
            ).order_by("team__order_index", "user_id")
        )

    @staticmethod
    def _pointer(company, code):
        from apps.distribution.models import RotationPointer

        p, _ = RotationPointer.objects.get_or_create(
            company=company, pointer_code=code, scope="GLOBAL",
            defaults={"current_index": 0},
        )
        return p

    @staticmethod
    def advance_pointer(company, code, length):
        """Move a rotation cursor forward by one (wraps). length=0 is a no-op."""
        p = WalkInService._pointer(company, code)
        if length:
            p.current_index = (p.current_index + 1) % length
            p.save(update_fields=["current_index", "updated_at"])
        return p.current_index

    @staticmethod
    def advance_for_policy(company, policy):
        """Advance the cursor for the receptionist 'skip / pass' action: full
        rotation skips a salesman, team turn passes to the next team."""
        if policy == FULL_ROTATION:
            WalkInService.advance_pointer(
                company, ROT_FULL, len(WalkInService.available_members(company)))
        elif policy == TEAM_TURN:
            from apps.accounts.models import Team

            WalkInService.advance_pointer(
                company, ROT_TEAM,
                Team.objects.filter(company=company, is_active=True).count())

    @staticmethod
    def rotation_state(company, policy):
        """Snapshot the receptionist needs: whose turn it is, plus the pool."""
        from apps.accounts.models import Team

        members = WalkInService.available_members(company)

        def person(m):
            return {"id": str(m.user_id),
                    "name": m.user.get_full_name() or m.user.email,
                    "team": m.team.name, "team_id": str(m.team_id)}

        if policy == FULL_ROTATION:
            idx = WalkInService._pointer(company, ROT_FULL).current_index
            idx = idx % len(members) if members else 0
            return {"policy": policy, "order": [person(m) for m in members],
                    "current_index": idx}
        if policy == TEAM_TURN:
            teams = list(Team.objects.filter(company=company, is_active=True)
                         .order_by("order_index"))
            tp = WalkInService._pointer(company, ROT_TEAM).current_index
            tp = tp % len(teams) if teams else 0
            cur = teams[tp] if teams else None
            mem = [person(m) for m in members if cur and m.team_id == cur.id]
            return {"policy": policy,
                    "teams": [{"id": str(t.id), "name": t.name} for t in teams],
                    "current_team": ({"id": str(cur.id), "name": cur.name}
                                     if cur else None),
                    "members": mem, "current_index": tp}
        return {"policy": policy, "salesmen": [person(m) for m in members]}

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
            print("[WALKIN TEAM TURN] No active teams found.")
            return None
        pointer, created = RotationPointer.objects.select_for_update().get_or_create(
            company=company, pointer_code="WALKIN_TEAM_TURN", scope="GLOBAL",
            defaults={"current_index": 0},
        )
        print(f"[WALKIN TEAM TURN START] Loaded Pointer ID: {pointer.id} | Current Index in DB: {pointer.current_index} (Created: {created})")
        print(f"   Active Teams: {[t.name for t in teams]}")

        for i in range(len(teams)):
            idx = pointer.current_index % len(teams)
            team = teams[idx]
            print(f"   - Checking team index {idx}: '{team.name}' (Pointer before advance: {pointer.current_index})")
            
            pointer.current_index = (idx + 1) % len(teams)
            pointer.save(update_fields=["current_index", "updated_at"])
            print(f"     Advanced pointer to: {pointer.current_index} and saved to DB.")

            # Check if this team has available salesmen
            pool = eligible_pool(
                company=company, team=team, scope_mode=ScopeMode.TEAM_THEN_SALESMAN
            )
            print(f"     Team '{team.name}' eligible pool size: {len(pool)} (Members: {[m.user.email for m in pool]})")
            if pool:
                print(f"[WALKIN TEAM TURN SELECTED] Selected Team: '{team.name}'")
                return team
        print("❌ [WALKIN TEAM TURN FAILED] No teams with available candidates.")
        return None
