"""FollowUp workflow (docs §9.3). Service-only: creating a follow-up sets the
lead to Follow-up stage, creates a reminder, audits, and notifies — none of which
a view may do directly."""
from __future__ import annotations

from django.db import transaction

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.notifications.constants import NotificationCode
from apps.notifications.services import NotificationService

from ..constants import StageCode
from ..models import FollowUp, Lead
from .lead_stage_service import LeadStageService
from .reminder_service import ReminderService


class FollowUpService:
    @staticmethod
    @transaction.atomic
    def schedule(*, lead_id, scheduled_at, actor=None, notes: str = "",
                 request_meta=None) -> FollowUp:
        lead = Lead.objects.select_for_update().select_related(
            "company", "assigned_salesman"
        ).get(id=lead_id)
        followup = FollowUp.objects.create(
            lead=lead, assigned_salesman=lead.assigned_salesman,
            scheduled_at=scheduled_at, notes=notes, created_by=actor,
        )
        LeadStageService.change_stage(
            lead_id=lead.id, to_stage_code=StageCode.FOLLOW_UP, actor=actor,
            reason="Follow-up scheduled", request_meta=request_meta,
        )
        ReminderService.create(
            company=lead.company, user=lead.assigned_salesman, due_at=scheduled_at,
            reminder_type="FOLLOWUP", lead=lead, related_type="FollowUp",
            related_id=followup.pk,
        )
        AuditService.log(
            action=AuditAction.CREATE, instance=followup, actor=actor,
            company=lead.company, module="leads", request_meta=request_meta,
        )
        NotificationService.create(
            company=lead.company, recipient=lead.assigned_salesman,
            code=NotificationCode.FOLLOWUP_DUE, title="Follow-up scheduled",
            related_type="Lead", related_id=lead.pk,
        )
        return followup

    @staticmethod
    @transaction.atomic
    def complete(*, followup_id, outcome: str = "", actor=None, move_to_stage=None,
                 request_meta=None) -> FollowUp:
        from django.utils import timezone

        followup = FollowUp.objects.select_related("lead").get(id=followup_id)
        followup.status = "COMPLETED"
        followup.outcome = outcome
        followup.completed_at = timezone.now()
        followup.save(update_fields=["status", "outcome", "completed_at", "updated_at"])
        if move_to_stage:
            LeadStageService.change_stage(
                lead_id=followup.lead_id, to_stage_code=move_to_stage, actor=actor,
                reason="Follow-up outcome", request_meta=request_meta,
            )
        AuditService.log(
            action=AuditAction.UPDATE, instance=followup, actor=actor,
            company=followup.lead.company, module="leads", request_meta=request_meta,
            after={"status": "COMPLETED", "outcome": outcome},
        )
        return followup
