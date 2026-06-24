"""Stage transitions + universal rotation rule (docs §9.1, §9.2). On SLA rotation
the visible stage resets to Fresh and the Fresh SLA restarts while all history is
preserved. Views never set stages directly."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.notifications.constants import NotificationCode
from apps.notifications.services import NotificationService

from ..constants import ActiveStatus, SLAStatus, StageCode
from ..models import Lead, LeadStageDefinition, LeadStageHistory
from .sla_service import SLAService


class LeadStageService:
    @staticmethod
    @transaction.atomic
    def change_stage(*, lead_id, to_stage_code: str, actor=None, reason: str = "",
                     request_meta=None) -> Lead:
        lead = Lead.objects.select_for_update().select_related(
            "company", "assigned_salesman", "current_stage"
        ).get(id=lead_id)
        to_stage = LeadStageDefinition.objects.get(code=to_stage_code)
        from_stage = lead.current_stage
        sla_before = lead.sla_deadline

        lead.current_stage = to_stage
        deadline = SLAService.calculate_deadline(
            lead.company, stage_code=to_stage_code, origin=lead.origin
        )
        # Not Interested is terminal -> lead becomes Inactive, no SLA (docs §9.1).
        if to_stage.is_terminal or to_stage_code == StageCode.NOT_INTERESTED:
            lead.active_status = ActiveStatus.INACTIVE
            lead.sla_deadline = None
            lead.sla_instances.filter(status=SLAStatus.ACTIVE).update(
                status=SLAStatus.CANCELLED
            )
        else:
            lead.sla_deadline = deadline
            SLAService.open_instance(lead=lead, stage=to_stage, deadline=deadline)
        lead.last_activity_at = timezone.now()
        lead.save(update_fields=[
            "current_stage", "active_status", "sla_deadline",
            "last_activity_at", "updated_at",
        ])

        LeadStageHistory.objects.create(
            lead=lead, from_stage=from_stage, to_stage=to_stage, actor=actor,
            reason=reason, sla_before=sla_before, sla_after=lead.sla_deadline,
        )
        AuditService.log(
            action=AuditAction.STAGE_CHANGE, instance=lead, actor=actor,
            company=lead.company, module="leads", request_meta=request_meta,
            before={"stage": getattr(from_stage, "code", None)},
            after={"stage": to_stage_code}, reason=reason,
        )
        NotificationService.create(
            company=lead.company, recipient=lead.assigned_salesman,
            code=NotificationCode.STAGE_CHANGED, title=f"Lead moved to {to_stage.name}",
            related_type="Lead", related_id=lead.pk,
        )
        return lead

    @staticmethod
    def reset_to_fresh(*, lead: Lead, actor=None, reason="SLA rotation") -> None:
        """Universal rotation rule (docs §9.2): reset visible stage to Fresh and
        restart the Fresh SLA. History is preserved by the caller's new
        assignment/stage records. Call inside an open transaction with a locked
        lead row."""
        fresh = LeadStageDefinition.objects.get(code=StageCode.FRESH)
        from_stage = lead.current_stage
        sla_before = lead.sla_deadline
        deadline = SLAService.calculate_deadline(
            lead.company, stage_code=StageCode.FRESH, origin=lead.origin
        )
        lead.current_stage = fresh
        lead.sla_deadline = deadline
        lead.last_activity_at = timezone.now()
        lead.save(update_fields=[
            "current_stage", "sla_deadline", "last_activity_at", "updated_at"
        ])
        SLAService.open_instance(lead=lead, stage=fresh, deadline=deadline)
        LeadStageHistory.objects.create(
            lead=lead, from_stage=from_stage, to_stage=fresh, actor=actor,
            reason=reason, sla_before=sla_before, sla_after=deadline,
        )
