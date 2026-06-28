"""Send the daily-task digest to one salesman only, for manual testing.

    python test_daily_email.py ahmedmohamedrashed2811@gmail.com
"""
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.utils import timezone

from apps.accounts.models import User
from apps.leads.constants import ActiveStatus
from apps.leads.models import FollowUp, Lead, Meeting, Reminder
from apps.notifications.tasks import (
    _daily_task_email_body_optimized,
    _daily_task_email_html,
    _send_email,
)


def main(email):
    user = User.objects.filter(email=email, is_active=True).first()
    if not user:
        sys.exit(f"No active user with email {email}")

    today = timezone.localtime().date()

    meetings = list(Meeting.objects.filter(
        assigned_salesman=user, scheduled_start__date=today, status="SCHEDULED"
    ).select_related("lead").order_by("scheduled_start"))
    followups = list(FollowUp.objects.filter(
        assigned_salesman=user, scheduled_at__date=today, status="SCHEDULED"
    ).select_related("lead").order_by("scheduled_at"))
    reminders = list(Reminder.objects.filter(
        user=user, reminder_type="STAGE_NOT_REACHED", due_at__date=today,
        status="PENDING"
    ).select_related("lead").order_by("due_at"))
    sla = list(Lead.objects.filter(
        assigned_salesman=user, active_status=ActiveStatus.ACTIVE,
        sla_deadline__date=today
    ).order_by("sla_deadline"))

    print(f"User {user.email}: {len(meetings)} meetings, {len(followups)} "
          f"follow-ups, {len(reminders)} not-reached, {len(sla)} SLA-today")

    body = _daily_task_email_body_optimized(
        user, today, meetings, followups, reminders, sla
    )
    if body is None:
        sys.exit("No tasks today — nothing to send. (Function returns None.)")

    html = _daily_task_email_html(user, today, meetings, followups, reminders, sla)
    _send_email(user.email, f"Your tasks for {today:%a, %d %b %Y}", body, html=html)
    print(f"Sent to {user.email}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ahmedmohamedrashed2811@gmail.com")
