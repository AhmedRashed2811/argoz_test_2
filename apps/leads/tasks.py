"""Celery entry points for lead SLA + reminders (docs §12.1). Tasks only call
services and record a JobExecutionLog; no business logic lives here."""
from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone


@shared_task(bind=True)
def check_lead_sla_expiry(self, batch_size: int = 100):
    """Beat every 1-5 min: rotate/reassign/escalate expired SLAs (docs §12.2).
    Locks each batch with skip_locked so workers never double-process."""
    from apps.audit.models import JobExecutionLog
    from apps.distribution.locks import expired_sla_batch
    from apps.distribution.services import SLAExpiryService

    task_id = getattr(self.request, "id", "") or ""
    processed = 0
    with transaction.atomic():
        for sla in expired_sla_batch(timezone.now(), limit=batch_size):
            if SLAExpiryService.process_instance(sla, task_id=task_id):
                processed += 1
    JobExecutionLog.objects.create(
        task_name="check_lead_sla_expiry", task_id=task_id, status="DONE",
        finished_at=timezone.now(), processed_count=processed,
    )
    return processed


@shared_task
def send_due_reminders():
    """Beat ~every minute: deliver due reminders (docs §12.1)."""
    from apps.leads.models import Reminder
    from apps.notifications.services import NotificationService
    from apps.notifications.constants import NotificationCode

    due = Reminder.objects.select_related("lead", "company", "user").filter(
        status="PENDING", due_at__lte=timezone.now()
    )[:500]
    count = 0
    for reminder in due:
        if reminder.user_id:
            code = NotificationCode.FOLLOWUP_DUE
            rtype = reminder.reminder_type
            if rtype in ("MEETING", "STAGE_MEETING"):
                code = NotificationCode.MEETING_DUE
            elif rtype in ("FOLLOWUP", "STAGE_FOLLOW_UP"):
                code = NotificationCode.FOLLOWUP_DUE
            elif rtype == "STAGE_FROZEN":
                code = NotificationCode.FROZEN_LEAD_RETURN
            elif rtype == "SLA_WARNING":
                code = NotificationCode.SLA_WARNING

            NotificationService.create(
                company=reminder.company, recipient=reminder.user,
                code=code,
                title=f"Reminder: {reminder.reminder_type}",
                related_type="Lead", related_id=reminder.lead_id or "",
            )
        reminder.status = "SENT"
        reminder.sent_at = timezone.now()
        reminder.save(update_fields=["status", "sent_at"])
        count += 1
    return count
