"""SLA deadline computation + instance lifecycle (docs §9, §12.2). Durations come
from policy (§7.2 lead.stage_sla.<code>, origin SLAs), never hardcoded."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.policies.constants import PolicyCode
from apps.policies.services import PolicyResolver

from ..constants import Origin, SLAStatus, StageCode
from ..models import Lead, LeadStageDefinition, SLAInstance


def _duration_to_timedelta(value, default_minutes: int = 60) -> timedelta:
    """Policy duration may be {'minutes': n} / {'hours': n} / int minutes."""
    if isinstance(value, dict):
        if "minutes" in value:
            return timedelta(minutes=int(value["minutes"]))
        if "hours" in value:
            return timedelta(hours=int(value["hours"]))
    if isinstance(value, (int, float)):
        return timedelta(minutes=int(value))
    return timedelta(minutes=default_minutes)


class SLAService:
    @staticmethod
    def stage_duration(company, stage_code: str) -> timedelta | None:
        # Not Interested has no SLA (docs §7.2).
        if stage_code == StageCode.NOT_INTERESTED:
            return None
        value = PolicyResolver.value(
            company, f"{PolicyCode.STAGE_SLA}.{stage_code.lower()}", default=None
        )
        return _duration_to_timedelta(value) if value is not None else None

    @staticmethod
    def origin_duration(company, origin: str) -> timedelta:
        code = (
            PolicyCode.BROKER_SLA if origin == Origin.BROKER else PolicyCode.DIRECT_SLA
        )
        return _duration_to_timedelta(PolicyResolver.value(company, code, default=None))

    @staticmethod
    def calculate_deadline(company, *, stage_code: str, origin: str | None = None):
        now = timezone.now()
        delta = None
        if stage_code == StageCode.FRESH and origin is not None:
            delta = SLAService.origin_duration(company, origin)
        if delta is None:
            delta = SLAService.stage_duration(company, stage_code)
        if delta is None and origin is not None:
            delta = SLAService.origin_duration(company, origin)
        return (now + delta) if delta else None

    @staticmethod
    def schedule_warnings(now) -> int:
        """Create SLA_WARNING Reminders for active SLAs within the warning window.
        Per-company threshold from policy 'lead.sla_warning_threshold' (default 30 min)."""
        from datetime import timedelta
        from apps.policies.services import PolicyResolver
        from ..models import Reminder
        from .reminder_service import ReminderService

        MAX_LOOKAHEAD = timedelta(hours=1)
        near_expiry = (
            SLAInstance.objects
            .select_related("lead", "lead__company", "lead__assigned_salesman")
            .filter(status=SLAStatus.ACTIVE, deadline_at__gt=now, deadline_at__lte=now + MAX_LOOKAHEAD)
        )
        count = 0
        for sla in near_expiry:
            if not sla.lead.assigned_salesman_id:
                continue
            threshold_val = PolicyResolver.value(
                sla.lead.company, "lead.sla_warning_threshold", default={"minutes": 30}
            )
            threshold = _duration_to_timedelta(threshold_val, default_minutes=30)
            if sla.deadline_at - threshold > now:
                continue  # too early
            already = Reminder.objects.filter(
                lead=sla.lead, reminder_type="SLA_WARNING",
                status__in=("PENDING", "SENT"),
            ).exists()
            if already:
                continue
            ReminderService.create(
                company=sla.lead.company, user=sla.lead.assigned_salesman,
                due_at=now, reminder_type="SLA_WARNING", lead=sla.lead,
            )
            count += 1
        return count

    @staticmethod
    def open_instance(*, lead: Lead, stage: LeadStageDefinition, deadline, salesman=None):
        """Close any active SLA, open a fresh one (idempotent rotation helper)."""
        SLAInstance.objects.filter(lead=lead, status=SLAStatus.ACTIVE).update(
            status=SLAStatus.COMPLETED
        )
        if deadline is None:
            return None
        return SLAInstance.objects.create(
            lead=lead,
            stage=stage,
            assigned_salesman=salesman or lead.assigned_salesman,
            start_at=timezone.now(),
            deadline_at=deadline,
            status=SLAStatus.ACTIVE,
        )
