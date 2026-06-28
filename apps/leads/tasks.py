"""Celery entry points for lead SLA + reminders (docs §12.1). Tasks only call
services and record a JobExecutionLog; no business logic lives here."""
from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone

# Map reminder_type → (NotificationCode attr, human title)
_REMINDER_MAP = {
    "MEETING":          ("MEETING_DUE",      "Meeting reminder"),
    "STAGE_MEETING":    ("MEETING_DUE",      "Meeting reminder"),
    "FOLLOWUP":         ("FOLLOWUP_DUE",     "Follow-up due"),
    "STAGE_FOLLOW_UP":  ("FOLLOWUP_DUE",     "Follow-up due"),
    "STAGE_NOT_REACHED":("FOLLOWUP_DUE",     "Unreached lead — follow-up due"),
    "STAGE_FRESH":      ("FOLLOWUP_DUE",     "Fresh lead requires attention"),
    "STAGE_FROZEN":     ("FROZEN_LEAD_RETURN","Frozen lead — action required"),
    "SLA_WARNING":      ("SLA_WARNING",      "SLA expiry warning"),
}


@shared_task(bind=True)
def expire_sla_instance(self, sla_instance_id):
    """Fired by an eta scheduled at the SLA deadline (docs §12.2): rotate /
    reassign / escalate this one expired SLA. process_instance is idempotent —
    a stale/revoked-but-still-fired run that finds the instance non-active is a
    harmless no-op. Each run gets its own savepoint."""
    from apps.audit.models import JobExecutionLog
    from apps.distribution.services import SLAExpiryService
    from apps.leads.models import SLAInstance
    from apps.leads.constants import SLAStatus

    task_id = getattr(self.request, "id", "") or ""
    print(f"\n⏰ [CELERY SLA EXPIRY START] Task ID: {task_id} | SLA Instance: {sla_instance_id}")
    sla = (
        SLAInstance.objects.select_related("lead", "lead__company", "lead__assigned_salesman")
        .filter(id=sla_instance_id, status=SLAStatus.ACTIVE)
        .first()
    )
    if sla is None:
        print(f"⚠️ SLA instance {sla_instance_id} not active (rotated/revoked) — skipping.\n")
        return False
    try:
        with transaction.atomic():
            print(f"👉 Processing expired SLA instance {sla.id} for Lead {sla.lead_id}...")
            result = bool(SLAExpiryService.process_instance(sla, task_id=task_id))
            print(f"🏁 [CELERY SLA EXPIRY DONE] SLA {sla.id} processed: {result}\n")
            return result
    except Exception as exc:
        print(f"❌ Error processing SLA instance {sla_instance_id}: {str(exc)}\n")
        JobExecutionLog.objects.create(
            task_name="expire_sla_instance", task_id=task_id,
            status="ERROR", finished_at=timezone.now(), error=str(exc)[:500],
        )
        raise


@shared_task
def schedule_sla_warnings():
    """Beat every ~minute: create SLA_WARNING reminders for near-expiry SLAs
    (docs §12.2). Expiry itself is now eta-scheduled per instance, not polled."""
    from apps.leads.services.sla_service import SLAService

    print(f"\n⏰ [CELERY SLA WARNINGS START]")
    warned = SLAService.schedule_warnings(timezone.now())
    print(f"🏁 [CELERY SLA WARNINGS DONE] Scheduled {warned} SLA warnings.\n")
    return warned


@shared_task
def send_due_reminders():
    """Beat ~every minute: deliver due reminders as in-app (and email when the
    reminder channel is EMAIL) notifications (docs §12.1)."""
    from apps.leads.models import Reminder
    from apps.notifications.constants import NotificationCode
    from apps.notifications.services import NotificationService

    print(f"\n⏰ [CELERY REMINDERS TASK START]")

    due = Reminder.objects.select_related("lead", "company", "user").filter(
        status="PENDING", due_at__lte=timezone.now()
    )[:500]
    due_list = list(due)
    print(f"📊 Found {len(due_list)} pending reminders due.")

    count = 0
    for reminder in due_list:
        if reminder.user_id:
            code_attr, title = _REMINDER_MAP.get(
                reminder.reminder_type,
                ("FOLLOWUP_DUE", f"Reminder: {reminder.reminder_type}"),
            )
            print(f"👉 Sending reminder {reminder.id} of type {reminder.reminder_type} to user {reminder.user_id}...")
            NotificationService.create(
                company=reminder.company,
                recipient=reminder.user,
                code=getattr(NotificationCode, code_attr),
                title=title,
                body=str(reminder.lead) if reminder.lead else "",
                related_type="Lead",
                related_id=reminder.lead_id or "",
                channels=[reminder.channel] if reminder.channel else None,
            )
        reminder.status = "SENT"
        reminder.sent_at = timezone.now()
        reminder.save(update_fields=["status", "sent_at"])
        count += 1
        print(f"✅ Reminder {reminder.id} status set to SENT.")

    print(f"🏁 [CELERY REMINDERS TASK DONE] Total sent: {count}\n")
    return count
