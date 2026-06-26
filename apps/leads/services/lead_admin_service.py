"""Admin "All Leads" controls (database view, leads spec §8). Service-only:
edit basic contact fields, attach notes, and activate/deactivate a lead — each
with an audit entry. Stage and assignment changes are delegated to their own
services so SLA/rotation/notification side-effects stay in one place. Views never
mutate the Lead directly."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.notifications.constants import NotificationCode
from apps.notifications.services import NotificationService

from ..constants import ActiveStatus, SLAStatus
from ..models import Lead, LeadNote


class LeadAdminService:
    @staticmethod
    @transaction.atomic
    def update_basic(*, lead_id, name=None, phone=None, email=None, note="",
                     actor=None, request_meta=None) -> Lead:
        """Update editable contact fields and optionally attach an internal note."""
        lead = Lead.objects.select_for_update().select_related("company").get(id=lead_id)
        before = {"name": lead.name, "phone": lead.phone, "email": lead.email}
        fields = []
        if name is not None and name != lead.name:
            lead.name = name
            fields.append("name")
        if phone is not None and phone != lead.phone:
            lead.phone = phone
            fields.append("phone")
        if email is not None and email != lead.email:
            lead.email = email
            fields.append("email")
        if fields:
            lead.last_activity_at = timezone.now()
            lead.save(update_fields=[*fields, "last_activity_at", "updated_at"])
            AuditService.log(
                action=AuditAction.UPDATE, instance=lead, actor=actor,
                company=lead.company, module="leads", request_meta=request_meta,
                before=before,
                after={"name": lead.name, "phone": lead.phone, "email": lead.email},
            )
        if note:
            LeadNote.objects.create(lead=lead, body=note, created_by=actor)
        return lead

    @staticmethod
    @transaction.atomic
    def set_active(*, lead_id, active: bool, reason="", actor=None,
                   request_meta=None) -> Lead:
        """Deactivate or reactivate a lead. Reactivation routes through
        ReactivationService (restores stage + SLA + notifies)."""
        if active:
            from .reactivation_service import ReactivationService
            return ReactivationService.reactivate(
                lead_id=lead_id, actor=actor, request_meta=request_meta,
            )
        lead = Lead.objects.select_for_update().select_related(
            "company", "assigned_salesman"
        ).get(id=lead_id)
        lead.active_status = ActiveStatus.INACTIVE
        lead.sla_deadline = None
        lead.last_activity_at = timezone.now()
        lead.save(update_fields=[
            "active_status", "sla_deadline", "last_activity_at", "updated_at",
        ])
        lead.sla_instances.filter(status=SLAStatus.ACTIVE).update(
            status=SLAStatus.CANCELLED
        )
        if note := reason:
            LeadNote.objects.create(lead=lead, body=note, created_by=actor)
        AuditService.log(
            action=AuditAction.UPDATE, instance=lead, actor=actor,
            company=lead.company, module="leads", request_meta=request_meta,
            after={"active_status": ActiveStatus.INACTIVE}, reason=reason,
        )
        NotificationService.create(
            company=lead.company, recipient=lead.assigned_salesman,
            code=NotificationCode.LEAD_REACTIVATED, title="Lead deactivated",
            related_type="Lead", related_id=lead.pk,
        )
        return lead
