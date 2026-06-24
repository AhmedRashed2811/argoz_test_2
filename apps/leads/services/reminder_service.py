"""Reminder creation per stage/policy (docs §9.3 ReminderService). Reminders are
swept by the send_due_reminders Celery task (§12)."""
from __future__ import annotations

from ..models import Reminder


class ReminderService:
    @staticmethod
    def create(*, company, user, due_at, reminder_type: str, lead=None,
               related_type: str = "", related_id=None, channel: str = "IN_APP") -> Reminder:
        return Reminder.objects.create(
            company=company, user=user, lead=lead, reminder_type=reminder_type,
            related_type=related_type, related_id=related_id, due_at=due_at,
            channel=channel,
        )

    @staticmethod
    def create_for_stage(*, lead, stage_code: str, due_at, channel="IN_APP"):
        if lead.assigned_salesman is None:
            return None
        return ReminderService.create(
            company=lead.company, user=lead.assigned_salesman, due_at=due_at,
            reminder_type=f"STAGE_{stage_code}", lead=lead, channel=channel,
        )
