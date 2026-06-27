"""By Turn (docs §8.3, §16.1): sequential fixed rotation over the eligible pool;
skip inactive/unavailable and advance the locked RotationPointer after success."""
from __future__ import annotations

from django.db import transaction

from ..interfaces import AssignmentDecision, AssignmentStrategyInterface
from ..models import RotationPointer


class ByTurnStrategy(AssignmentStrategyInterface):
    code = "BY_TURN"

    def select_candidate(self, *, company, lead, eligible_pool, context):
        pool = list(eligible_pool)
        if not pool:
            return AssignmentDecision(reason="No eligible candidate")
        # The rotation cursor must be per-pool: a lead's language (and scope mode)
        # changes which salesmen are eligible, so a single GLOBAL pointer shared
        # across differently-sized pools desyncs the turn (e.g. a 1-person language
        # pool resets it every time and starves the tail of the larger pool).
        lang = getattr(context.language, "code", None) or "ANY"
        scope = context.params.get("pointer_scope") or f"{context.scope_mode or 'ALL'}:{lang}"
        # Lock the pointer row so concurrent runs can't pick the same turn (§17).
        with transaction.atomic():
            pointer, _ = RotationPointer.objects.select_for_update().get_or_create(
                company=company, pointer_code=self.code, scope=scope,
                defaults={"current_index": 0},
            )
            idx = pointer.current_index % len(pool)
            member = pool[idx]
            pointer.current_index = (idx + 1) % len(pool)
            pointer.save(update_fields=["current_index", "updated_at"])
        return AssignmentDecision(
            team=member.team, salesman=member.user,
            reason="By Turn Rotation", snapshot={"index": idx, "scope": scope},
        )
