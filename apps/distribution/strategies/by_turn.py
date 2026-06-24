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
        scope = context.params.get("pointer_scope", "GLOBAL")
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
            reason=f"By Turn index {idx}", snapshot={"index": idx, "scope": scope},
        )
