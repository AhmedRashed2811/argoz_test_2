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


@shared_task(bind=True)
def send_sla_reminder(self, sla_instance_id):
    """Fired by an eta scheduled at (deadline - warning threshold) when the SLA
    is opened (docs §12.2): create the SLA_WARNING reminder for this one
    instance. No-op if the SLA already rotated away from this instance."""
    from apps.leads.models import Reminder, SLAInstance
    from apps.leads.constants import SLAStatus
    from apps.leads.services.reminder_service import ReminderService

    sla = (
        SLAInstance.objects.select_related("lead", "lead__company", "lead__assigned_salesman")
        .filter(id=sla_instance_id, status=SLAStatus.ACTIVE)
        .first()
    )
    if sla is None or not sla.lead.assigned_salesman_id:
        return False
    already = Reminder.objects.filter(
        lead=sla.lead, user=sla.lead.assigned_salesman, reminder_type="SLA_WARNING",
        status__in=("PENDING", "SENT"),
    ).exists()
    if already:
        return False
    ReminderService.create(
        company=sla.lead.company, user=sla.lead.assigned_salesman,
        due_at=timezone.now(), reminder_type="SLA_WARNING", lead=sla.lead,
    )
    return True


def _deliver_reminder(reminder) -> None:
    """Send one PENDING reminder as a notification and mark it SENT. Shared by
    the eta-scheduled deliver_reminder task and the send_due_reminders safety
    net sweep."""
    from apps.notifications.constants import NotificationCode
    from apps.notifications.services import NotificationService

    if reminder.user_id:
        code_attr, title = _REMINDER_MAP.get(
            reminder.reminder_type,
            ("FOLLOWUP_DUE", f"Reminder: {reminder.reminder_type}"),
        )
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


@shared_task
def deliver_reminder(reminder_id):
    """Fired by an eta scheduled at Reminder.due_at when the reminder is
    created (docs §12.1): deliver this one reminder on time instead of
    waiting for the next polling sweep. No-op if already delivered."""
    from apps.leads.models import Reminder

    reminder = (
        Reminder.objects.select_related("lead", "company", "user")
        .filter(id=reminder_id, status="PENDING")
        .first()
    )
    if reminder is None:
        return False
    _deliver_reminder(reminder)
    return True


@shared_task
def send_due_reminders():
    """Beat ~every minute: safety-net sweep in case an eta-scheduled
    deliver_reminder job was lost (e.g. broker restart). Normally a no-op
    since reminders are delivered on time via their own eta job."""
    from apps.leads.models import Reminder

    print(f"\n⏰ [CELERY REMINDERS TASK START]")

    due = Reminder.objects.select_related("lead", "company", "user").filter(
        status="PENDING", due_at__lte=timezone.now()
    )[:500]
    due_list = list(due)
    print(f"📊 Found {len(due_list)} pending reminders due.")

    count = 0
    for reminder in due_list:
        _deliver_reminder(reminder)
        count += 1
        print(f"✅ Reminder {reminder.id} status set to SENT.")

    print(f"🏁 [CELERY REMINDERS TASK DONE] Total sent: {count}\n")
    return count
