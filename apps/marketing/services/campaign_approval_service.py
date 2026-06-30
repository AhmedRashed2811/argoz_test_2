"""Finance approval (docs §10.4, §11.4). Reason is mandatory for Semi Approved
and Not Approved; every decision snapshots the budget, audits, and notifies.
Only this service writes approval_status."""
from __future__ import annotations

from django.db import transaction

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.core.exceptions import ValidationError
from apps.notifications.constants import NotificationCode
from apps.notifications.services import NotificationService

from ..constants import ApprovalStatus
from ..models import Campaign, CampaignApprovalHistory
from .campaign_budget_service import CampaignBudgetService

_NOTIF = {
    ApprovalStatus.APPROVED: NotificationCode.CAMPAIGN_APPROVED,
    ApprovalStatus.SEMI_APPROVED: NotificationCode.CAMPAIGN_SEMI_APPROVED,
    ApprovalStatus.NOT_APPROVED: NotificationCode.CAMPAIGN_REJECTED,
}


class CampaignApprovalService:
    @staticmethod
    def approval_required(company) -> bool:
        """Whether the company runs campaigns through finance approval (docs §10.4)."""
        from apps.policies.constants import PolicyCode
        from apps.policies.services import PolicyResolver
        return bool(PolicyResolver.value(
            company, PolicyCode.REQUEST_CAMPAIGN_APPROVAL, default=True))

    @staticmethod
    def restrict_editing(company) -> bool:
        """Editing is restricted only when approval is required AND the company
        opts to lock approved campaigns. No approval flow => fully editable."""
        from apps.policies.constants import PolicyCode
        from apps.policies.services import PolicyResolver
        if not CampaignApprovalService.approval_required(company):
            return False
        return bool(PolicyResolver.value(
            company, PolicyCode.CAMPAIGN_RESTRICT_EDITING, default=True))

    @staticmethod
    @transaction.atomic
    def submit_for_finance(*, campaign_id, actor=None, request_meta=None) -> Campaign:
        from .campaign_creation_service import CampaignCreationService

        campaign = Campaign.objects.select_for_update().get(id=campaign_id)
        if not CampaignApprovalService.approval_required(campaign.company):
            raise ValidationError("Campaign approval is disabled for this company.")
        CampaignCreationService.assert_submittable(campaign)
        CampaignBudgetService.recalculate(campaign=campaign, actor=actor)
        AuditService.log(
            action=AuditAction.UPDATE, instance=campaign, actor=actor,
            company=campaign.company, module="finance", request_meta=request_meta,
            after={"submitted_for_finance": True},
        )
        NotificationService.create_for_users(
            company=campaign.company, recipients=_finance_managers(campaign.company),
            exclude_user=actor, code=NotificationCode.CAMPAIGN_SUBMITTED_FINANCE,
            title=f"Campaign submitted: {campaign.name}",
            related_type="Campaign", related_id=campaign.pk,
        )
        return campaign

    @staticmethod
    def reset_to_pending_on_edit(*, campaign, actor=None, request_meta=None) -> bool:
        """Task 5: any content edit to a campaign finance already decided sends it
        back to Pending for re-approval. Leads count and real attendance never
        flow through the campaign editor, so any edit that reaches here qualifies.
        Emits the audit entry, approval-history row and a finance notification."""
        if not CampaignApprovalService.approval_required(campaign.company):
            return False
        decided = (ApprovalStatus.APPROVED, ApprovalStatus.SEMI_APPROVED,
                   ApprovalStatus.NOT_APPROVED)
        from_status = campaign.approval_status
        if from_status not in decided:
            return False
        campaign.approval_status = ApprovalStatus.PENDING
        campaign.approval_reason = ""
        campaign.rejected_budgets = []
        campaign.save(update_fields=["approval_status", "approval_reason",
                                     "rejected_budgets", "updated_at"])
        CampaignApprovalHistory.objects.create(
            campaign=campaign, from_status=from_status,
            to_status=ApprovalStatus.PENDING,
            reason="Reset to Pending — campaign edited after a finance decision.",
            actor=actor,
        )
        AuditService.log(
            action=AuditAction.UPDATE, instance=campaign, actor=actor,
            company=campaign.company, module="marketing", request_meta=request_meta,
            before={"approval_status": from_status},
            after={"approval_status": ApprovalStatus.PENDING},
            reason="Edited after a finance decision; re-approval required.",
        )
        NotificationService.create_for_users(
            company=campaign.company, recipients=_finance_managers(campaign.company),
            exclude_user=actor, code=NotificationCode.CAMPAIGN_SUBMITTED_FINANCE,
            title=f"Campaign edited — re-approval needed: {campaign.name}",
            related_type="Campaign", related_id=campaign.pk,
        )
        return True

    @staticmethod
    @transaction.atomic
    def set_status(*, campaign_id, status: str, actor=None, reason: str = "",
                   rejected_budgets=None, request_meta=None) -> Campaign:
        if status not in dict(ApprovalStatus.CHOICES):
            raise ValidationError(f"Unknown approval status: {status}")
        if status in ApprovalStatus.REASON_REQUIRED and not reason.strip():
            raise ValidationError(
                "Reason is mandatory for Semi Approved / Not Approved (docs §10.4)."
            )
        campaign = Campaign.objects.select_for_update().get(id=campaign_id)
        from_status = campaign.approval_status
        snapshot = CampaignBudgetService.recalculate(campaign=campaign, actor=actor)

        campaign.approval_status = status
        campaign.approval_reason = reason
        
        if status == ApprovalStatus.SEMI_APPROVED and rejected_budgets is not None:
            campaign.rejected_budgets = rejected_budgets
        elif status in (ApprovalStatus.APPROVED, ApprovalStatus.NOT_APPROVED, ApprovalStatus.PENDING):
            campaign.rejected_budgets = []
            
        campaign.save(update_fields=["approval_status", "approval_reason", "rejected_budgets", "updated_at"])

        CampaignApprovalHistory.objects.create(
            campaign=campaign, from_status=from_status, to_status=status,
            reason=reason, budget_snapshot={"total_budget": float(snapshot)}, actor=actor,
        )
        AuditService.log(
            action=AuditAction.APPROVE, instance=campaign, actor=actor,
            company=campaign.company, module="finance", request_meta=request_meta,
            before={"approval_status": from_status},
            after={"approval_status": status}, reason=reason,
        )
        if status == ApprovalStatus.APPROVED:
            recipients = _campaign_approved_recipients(campaign.company)
        else:
            recipients = _marketing_team(campaign.company)

        NotificationService.create_for_users(
            company=campaign.company, recipients=recipients,
            exclude_user=actor, code=_NOTIF.get(status, NotificationCode.CAMPAIGN_APPROVED),
            title=f"Campaign {status}: {campaign.name}",
            related_type="Campaign", related_id=campaign.pk,
        )
        return campaign


def _perm_users(company, code):
    from apps.accounts.models import User
    from apps.authorization.services import EffectivePermissionResolver

    users = User.objects.filter(is_active=True, profile__company=company).distinct()
    return [u for u in users if EffectivePermissionResolver.has(u, code)]


def _finance_managers(company):
    return _perm_users(company, "finance.campaign.approve")


def _marketing_team(company):
    return _perm_users(company, "marketing.campaigns.access")


def _campaign_approved_recipients(company):
    from apps.accounts.models import User
    from django.db.models import Q
    role_codes = ["FINANCE_MANAGERS", "DIRECTORS", "MARKETING_MEMBERS", "MARKETING_MANAGERS"]
    return list(User.objects.filter(
        is_active=True,
        profile__company=company
    ).filter(
        Q(profile__default_role__code__in=role_codes) |
        Q(roles__role__code__in=role_codes, roles__is_active=True)
    ).distinct())
