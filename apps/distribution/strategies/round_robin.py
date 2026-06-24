"""Round Robin (docs §8.3, §16.1): fewest active leads wins, tie-break by
earliest last-received lead time."""
from __future__ import annotations

from datetime import datetime
from datetime import timezone as _tz

from ..interfaces import AssignmentDecision, AssignmentStrategyInterface
from ..selectors import batch_candidate_loads

_MIN_DT = datetime.min.replace(tzinfo=_tz.utc)


class RoundRobinStrategy(AssignmentStrategyInterface):
    code = "ROUND_ROBIN"

    def select_candidate(self, *, company, lead, eligible_pool, context):
        if not eligible_pool:
            return AssignmentDecision(reason="No eligible candidate")
        # Batch-fetch loads in 2 queries instead of 2N (docs §8.3).
        loads = batch_candidate_loads([m.user for m in eligible_pool], company)
        best = None
        best_key = None
        snapshot = {}
        for member in eligible_pool:
            active_count, last_received = loads.get(member.user_id, (0, None))
            snapshot[str(member.user_id)] = {
                "active": active_count,
                "last_received": last_received.isoformat() if last_received else None,
            }
            # Sort key: (active leads asc, last_received asc — None first).
            key = (active_count, last_received or _MIN_DT)
            if best_key is None or key < best_key:
                best_key, best = key, member
        if best is None:
            return AssignmentDecision(reason="No eligible candidate")
        return AssignmentDecision(
            team=best.team, salesman=best.user,
            reason="Round Robin: fewest active leads", snapshot=snapshot,
        )
