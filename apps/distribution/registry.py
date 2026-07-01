"""Strategy registry (docs §16). Registers built-in strategies into the shared
policy registry by stable code and resolves the active class for a code."""
from apps.policies.registry import register, resolve_class

from .interfaces import AssignmentStrategyInterface

# Static safe registry (docs §16.1): works before any StrategyDefinition rows.
register("ROUND_ROBIN", "apps.distribution.strategies.round_robin.RoundRobinStrategy")
register("BY_TURN", "apps.distribution.strategies.by_turn.ByTurnStrategy")


class StrategyRegistry:
    @staticmethod
    def get(code: str):
        strategy_cls = resolve_class(code)
        if not issubclass(strategy_cls, AssignmentStrategyInterface):
            raise TypeError(
                f"Distribution strategy {code} must implement AssignmentStrategyInterface."
            )
        return strategy_cls()
