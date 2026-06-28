"""Meeting workflow (docs §9.3). Service-only, mirrors FollowUpService: sets
Meeting stage, creates reminder, audits, notifies salesman (+ optional head/
receptionist)."""
from __future__ import annotations

from django.db import transaction

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.core.exceptions import ValidationError
from apps.notifications.constants import NotificationCode
from apps.notifications.services import NotificationService

from ..constants import StageCode
from ..models import Lead, Meeting
from .lead_stage_service import LeadStageService
from .reminder_service import ReminderService


class MeetingService:
    @staticmethod
    @transaction.atomic
    def schedule(*, lead_id, scheduled_start, scheduled_end=None, location: str = "",
                 actor=None, request_meta=None) -> Meeting:
        if scheduled_end and scheduled_end < scheduled_start:
            raise ValidationError("Meeting end cannot precede start.")
        lead = Lead.objects.select_for_update().select_related(
            "company", "assigned_salesman"
        ).get(id=lead_id)
        from .sales_action_policy_service import (
            enforce_action_limit, enforce_max_duration,
        )
        enforce_action_limit(lead=lead, salesman=lead.assigned_salesman,
                             actor=actor, action="meeting")
        enforce_max_duration(company=lead.company, actor=actor, action="meeting",
                             scheduled_at=scheduled_start)
        meeting = Meeting.objects.create(
            lead=lead, assigned_salesman=lead.assigned_salesman,
            scheduled_start=scheduled_start, scheduled_end=scheduled_end,
            location=location, created_by=actor,
        )
        LeadStageService.change_stage(
            lead_id=lead.id, to_stage_code=StageCode.MEETING, actor=actor,
            reason="Meeting scheduled", request_meta=request_meta,
            scheduled_time=scheduled_start
        )
        ReminderService.create(
            company=lead.company, user=lead.assigned_salesman, due_at=scheduled_start,
            reminder_type="MEETING", lead=lead, related_type="Meeting",
            related_id=meeting.pk,
        )
        AuditService.log(
            action=AuditAction.CREATE, instance=meeting, actor=actor,
            company=lead.company, module="leads", request_meta=request_meta,
        )
        return meeting
