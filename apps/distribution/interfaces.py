"""Distribution strategy contract (docs §16.1). New techniques implement this
and register by stable code; existing workflows never change."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssignmentDecision:
    team: Any = None
    salesman: Any = None
    reason: str = ""
    snapshot: dict = field(default_factory=dict)


@dataclass
class DistributionContext:
    company: Any
    scope_mode: str = ""
    language: Any = None
    actor: Any = None
    params: dict = field(default_factory=dict)


class AssignmentStrategyInterface:
    code: str = ""

    def select_candidate(self, *, company, lead, eligible_pool, context):
        """Return an AssignmentDecision. eligible_pool is the language/scope-
        filtered list of candidate TeamMember rows (docs §8.4)."""
        raise NotImplementedError
