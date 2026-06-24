"""Frozen-lead return + inactive reactivation (docs §9.1 Frozen, §12.3
FROZEN_LEAD_RETURN / LEAD_REACTIVATED)."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.notifications.constants import NotificationCode
from apps.notifications.services import NotificationService

from ..constants import ActiveStatus, StageCode
from ..models import Lead
from .lead_stage_service import LeadStageService


class ReactivationService:
    @staticmethod
    @transaction.atomic
    def reactivate(*, lead_id, actor=None, to_stage_code=StageCode.FRESH,
                   request_meta=None) -> Lead:
        lead = Lead.objects.select_for_update().select_related(
            "company", "assigned_salesman"
        ).get(id=lead_id)
        lead.active_status = ActiveStatus.ACTIVE
        lead.last_activity_at = timezone.now()
        lead.save(update_fields=["active_status", "last_activity_at", "updated_at"])
        LeadStageService.change_stage(
            lead_id=lead.id, to_stage_code=to_stage_code, actor=actor,
            reason="Reactivated", request_meta=request_meta,
        )
        AuditService.log(
            action=AuditAction.UPDATE, instance=lead, actor=actor,
            company=lead.company, module="leads", request_meta=request_meta,
            after={"active_status": ActiveStatus.ACTIVE},
        )
        NotificationService.create_for_users(
            company=lead.company, recipients=[lead.assigned_salesman],
            code=NotificationCode.LEAD_REACTIVATED, title="Lead reactivated",
            related_type="Lead", related_id=lead.pk,
        )
        return lead

    @staticmethod
    def notify_frozen_return(*, lead: Lead) -> None:
        NotificationService.create(
            company=lead.company, recipient=lead.assigned_salesman,
            code=NotificationCode.FROZEN_LEAD_RETURN, title="Frozen lead ready to re-engage",
            related_type="Lead", related_id=lead.pk,
        )
