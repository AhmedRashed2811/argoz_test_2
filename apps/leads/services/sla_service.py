"""SLA deadline computation + instance lifecycle (docs §9, §12.2). Durations come
from policy (§7.2 lead.stage_sla.<code>, origin SLAs), never hardcoded."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.policies.constants import PolicyCode
from apps.policies.services import PolicyResolver

from ..constants import Origin, SLAStatus, StageCode, SourceCode
from ..models import Lead, LeadStageDefinition, SLAInstance


def _duration_to_timedelta(value, default_minutes: int = 60) -> timedelta:
    """Policy duration may be {'days': n}/{'hours': n}/{'minutes': n} / int minutes."""
    if isinstance(value, dict):
        d = int(value.get("days") or 0)
        h = int(value.get("hours") or 0)
        m = int(value.get("minutes") or 0)
        return timedelta(days=d, hours=h, minutes=m)
    if isinstance(value, (int, float)):
        return timedelta(minutes=int(value))
    return timedelta(minutes=default_minutes)


def _apply_weekend_freeze(company, start, end):
    """Push `end` forward so configured weekend day(s) don't count against the
    SLA (task 16e). No-op unless the policy is enabled with weekend days."""
    cfg = PolicyResolver.value(company, PolicyCode.WEEKEND_SLA_FREEZE, default=None)
    if not (isinstance(cfg, dict) and cfg.get("enabled")):
        return end
    weekend = {int(d) for d in (cfg.get("weekend_days") or [])}
    if not weekend:
        return end
    new_end = end
    day = start.date()
    while day <= new_end.date():
        if day.weekday() in weekend:
            new_end += timedelta(days=1)
        day += timedelta(days=1)
    return new_end


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
    def calculate_deadline(company, *, stage_code: str, origin: str | None = None, source_code: str | None = None, frozen_days: int = 0, scheduled_time=None):
        now = timezone.now()
        delta = None
        if stage_code == StageCode.FRESH:
            if source_code == SourceCode.WALK_IN:
                delta = _duration_to_timedelta(PolicyResolver.value(company, PolicyCode.WALKIN_SLA, default=None))
            elif origin is not None:
                delta = SLAService.origin_duration(company, origin)
        if delta is None:
            delta = SLAService.stage_duration(company, stage_code)
        if delta is None:
            if source_code == SourceCode.WALK_IN:
                delta = _duration_to_timedelta(PolicyResolver.value(company, PolicyCode.WALKIN_SLA, default=None))
            elif origin is not None:
                delta = SLAService.origin_duration(company, origin)
        if stage_code == StageCode.FROZEN and frozen_days > 0:
            if delta is None:
                delta = timedelta(0)
            delta += timedelta(days=frozen_days)
        if stage_code in (StageCode.MEETING, StageCode.FOLLOW_UP) and scheduled_time:
            if delta is None:
                delta = timedelta(0)
            delta += (scheduled_time - now)
        if not delta:
            return None
        return _apply_weekend_freeze(company, now, now + delta)

    @staticmethod
    def warning_threshold(company, stage_code: str) -> timedelta:
        """How long before deadline_at the SLA_WARNING reminder should fire.
        Per-company policy: 'lead.fresh_reminder_schedule' for Fresh, else
        'lead.sla_warning_threshold'."""
        if stage_code == StageCode.FRESH:
            threshold_val = PolicyResolver.value(
                company, PolicyCode.FRESH_REMINDER_SCHEDULE, default={"minutes": 2}
            )
        else:
            threshold_val = PolicyResolver.value(
                company, "lead.sla_warning_threshold", default={"minutes": 30}
            )
        return _duration_to_timedelta(threshold_val, default_minutes=30)

    @staticmethod
    def _revoke_expiry(task_id: str) -> None:
        if not task_id:
            return
        from config.celery import app
        app.control.revoke(task_id)

    @staticmethod
    def open_instance(*, lead: Lead, stage: LeadStageDefinition, deadline, salesman=None):
        """Close any active SLA, open a fresh one (idempotent rotation helper).
        Revokes the outgoing SLA's eta expiry job and schedules a new one at the
        new deadline (docs §12.2)."""
        from apps.leads.tasks import expire_sla_instance, send_sla_reminder

        # Revoke any pending eta expiry/reminder job(s) before closing the old SLA(s).
        for old_task_id in SLAInstance.objects.filter(
            lead=lead, status=SLAStatus.ACTIVE
        ).exclude(expiry_task_id="").values_list("expiry_task_id", flat=True):
            SLAService._revoke_expiry(old_task_id)
        for old_task_id in SLAInstance.objects.filter(
            lead=lead, status=SLAStatus.ACTIVE
        ).exclude(reminder_task_id="").values_list("reminder_task_id", flat=True):
            SLAService._revoke_expiry(old_task_id)
        SLAInstance.objects.filter(lead=lead, status=SLAStatus.ACTIVE).update(
            status=SLAStatus.COMPLETED
        )
        if deadline is None:
            return None
        owner = salesman or lead.assigned_salesman
        instance = SLAInstance.objects.create(
            lead=lead,
            stage=stage,
            assigned_salesman=owner,
            start_at=timezone.now(),
            deadline_at=deadline,
            status=SLAStatus.ACTIVE,
        )
        # Reminder fires at deadline_at minus the company's warning threshold,
        # replacing the old minute-by-minute poll (docs §12.2).
        reminder_eta = None
        if owner is not None:
            threshold = SLAService.warning_threshold(lead.company, stage.code)
            candidate = deadline - threshold
            reminder_eta = candidate if candidate > timezone.now() else timezone.now()

        # Schedule expiry/reminder exactly on time. Defer enqueue to after commit
        # so the worker can never pick up the instance before it's visible.
        from django.db import transaction

        def _schedule():
            result = expire_sla_instance.apply_async(
                args=[str(instance.id)], eta=instance.deadline_at
            )
            update_fields = {"expiry_task_id": result.id}
            if reminder_eta is not None:
                reminder_result = send_sla_reminder.apply_async(
                    args=[str(instance.id)], eta=reminder_eta
                )
                update_fields["reminder_task_id"] = reminder_result.id
            SLAInstance.objects.filter(id=instance.id).update(**update_fields)

        transaction.on_commit(_schedule)
        return instance
