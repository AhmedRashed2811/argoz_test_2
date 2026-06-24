"""Duplicate detection before lead creation (docs §8.1). An active, in-SLA
duplicate is a 'Call Me Again' case that must escalate to manual distribution
users, not auto Round Robin (§8.1, §12.3 MANUAL_DISTRIBUTION_REQUIRED)."""
from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from ..constants import ActiveStatus
from ..models import Lead


@dataclass
class DuplicateResult:
    is_duplicate: bool
    existing: Lead | None = None
    requires_manual: bool = False


class DuplicateService:
    @staticmethod
    def check(*, company, phone: str) -> DuplicateResult:
        existing = (
            Lead.objects.filter(company=company, phone=phone)
            .order_by("-created_at")
            .first()
        )
        if existing is None:
            return DuplicateResult(is_duplicate=False)
        active = existing.active_status == ActiveStatus.ACTIVE
        within_sla = bool(existing.sla_deadline and existing.sla_deadline > timezone.now())
        return DuplicateResult(
            is_duplicate=True,
            existing=existing,
            requires_manual=active and within_sla,
        )
