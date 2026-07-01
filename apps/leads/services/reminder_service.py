"""Reminder creation per stage/policy (docs §9.3 ReminderService). Each reminder
is eta-scheduled for delivery at due_at (docs §12); send_due_reminders is only
a safety-net sweep."""
from __future__ import annotations

from django.db import transaction

from ..models import Reminder


class ReminderService:
    @staticmethod
    def create(*, company, user, due_at, reminder_type: str, lead=None,
               related_type: str = "", related_id=None, channel: str = "IN_APP") -> Reminder:
        from ..tasks import deliver_reminder

        reminder = Reminder.objects.create(
            company=company, user=user, lead=lead, reminder_type=reminder_type,
            related_type=related_type, related_id=related_id, due_at=due_at,
            channel=channel,
        )
        transaction.on_commit(
            lambda: deliver_reminder.apply_async(args=[str(reminder.id)], eta=due_at)
        )
        return reminder

    @staticmethod
    def create_for_stage(*, lead, stage_code: str, due_at, channel="IN_APP"):
        if lead.assigned_salesman is None:
            return None
        return ReminderService.create(
            company=lead.company, user=lead.assigned_salesman, due_at=due_at,
            reminder_type=f"STAGE_{stage_code}", lead=lead, channel=channel,
        )
