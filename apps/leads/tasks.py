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
def check_lead_sla_expiry(self, batch_size: int = 100):
    """Beat every 1-5 min: rotate/reassign/escalate expired SLAs, and schedule
    SLA_WARNING reminders for near-expiry instances (docs §12.2).
    Each SLA is processed in its own savepoint so one failure never blocks others."""
    from apps.audit.models import JobExecutionLog
    from apps.distribution.locks import expired_sla_batch
    from apps.distribution.services import SLAExpiryService
    from apps.leads.services.sla_service import SLAService

    task_id = getattr(self.request, "id", "") or ""
    now = timezone.now()
    processed = 0

    print(f"\n⏰ [CELERY SLA TASK START] Task ID: {task_id} | Batch Size Limit: {batch_size}")

    with transaction.atomic():
        expired_slas = list(expired_sla_batch(now, limit=batch_size))
        print(f"📊 Found {len(expired_slas)} expired SLA instances to process.")
        for sla in expired_slas:
            try:
                with transaction.atomic():
                    print(f"👉 Processing SLA instance {sla.id} for Lead {sla.lead_id}...")
                    if SLAExpiryService.process_instance(sla, task_id=task_id):
                        processed += 1
                        print(f"✅ Successfully processed SLA instance {sla.id}.")
                    else:
                        print(f"⚠️ SLA instance {sla.id} was not active or skipped.")
            except Exception as exc:
                print(f"❌ Error processing SLA instance {sla.id}: {str(exc)}")
                JobExecutionLog.objects.create(
                    task_name="check_lead_sla_expiry", task_id=task_id,
                    status="ERROR", finished_at=timezone.now(), error=str(exc)[:500],
                )

    print(f"🕒 Scheduling warnings...")
    warned = SLAService.schedule_warnings(now)
    print(f"📢 Scheduled {warned} SLA warnings.")

    JobExecutionLog.objects.create(
        task_name="check_lead_sla_expiry", task_id=task_id, status="DONE",
        finished_at=timezone.now(), processed_count=processed,
        metadata={"sla_warnings_scheduled": warned},
    )
    print(f"🏁 [CELERY SLA TASK DONE] Processed: {processed} | Warned: {warned}\n")
    return processed


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
