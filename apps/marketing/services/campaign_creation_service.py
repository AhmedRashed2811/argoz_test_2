"""Campaign creation (docs §10.1, §10.3). Receives a nested payload of selected
types + children; heavy child-record creation lives here, not in views. Validates
dates and type completeness, recalculates budget, audits, notifies."""
from __future__ import annotations

from django.db import transaction

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.core.exceptions import ValidationError
from apps.notifications.constants import NotificationCode
from apps.notifications.services import NotificationService

from ..models import Campaign, CampaignSelectedType
from .campaign_budget_service import CampaignBudgetService


class CampaignCreationService:
    @staticmethod
    @transaction.atomic
    def create_campaign(*, company, name, start_date, end_date, actor=None,
                        selected_types=None, request_meta=None, **fields) -> Campaign:
        from apps.policies.constants import PolicyCode
        from apps.policies.services import PolicyResolver
        from ..constants import ApprovalStatus

        if end_date < start_date:
            raise ValidationError("Campaign end_date cannot precede start_date (§10.1).")
        # When the company doesn't require campaign approval, skip the finance flow
        # entirely: campaigns are approved by default and stay fully editable.
        approval_required = PolicyResolver.value(
            company, PolicyCode.REQUEST_CAMPAIGN_APPROVAL, default=True)
        if not approval_required:
            fields.setdefault("approval_status", ApprovalStatus.APPROVED)
        campaign = Campaign.objects.create(
            company=company, name=name, start_date=start_date, end_date=end_date,
            created_by=actor, **fields,
        )
        for type_code in (selected_types or []):
            CampaignSelectedType.objects.create(campaign=campaign, type_code=type_code)

        # Children are appended through their own services after creation; we
        # recalc the budget so a freshly-created campaign has a snapshot.
        CampaignBudgetService.recalculate(campaign=campaign, actor=actor)

        AuditService.log(
            action=AuditAction.CREATE, instance=campaign, actor=actor, company=company,
            module="marketing", request_meta=request_meta,
            after={"name": name, "types": list(selected_types or [])},
        )
        NotificationService.create_for_users(
            company=company, recipients=_campaign_created_recipients(company), exclude_user=actor,
            code=NotificationCode.CAMPAIGN_CREATED, title=f"Campaign created: {name}",
            related_type="Campaign", related_id=campaign.pk,
        )
        return campaign

    @staticmethod
    @transaction.atomic
    def update_campaign(*, campaign: Campaign, actor=None, request_meta=None,
                        **fields) -> Campaign:
        allowed = {"name", "description", "start_date", "end_date", "target_type", "target_id"}
        update_fields = [k for k in fields if k in allowed]
        for k in update_fields:
            setattr(campaign, k, fields[k])
        if update_fields:
            campaign.save(update_fields=update_fields + ["updated_at"])
        AuditService.log(
            action=AuditAction.UPDATE, instance=campaign, actor=actor, company=campaign.company,
            module="marketing", request_meta=request_meta,
            after={k: str(fields[k]) for k in update_fields},
        )
        return campaign

    @staticmethod
    def assert_submittable(campaign: Campaign) -> None:
        """At least one type selected before finance submission (docs §10.1, §17)."""
        if not campaign.selected_types.exists():
            raise ValidationError("Select at least one campaign type before submission.")
        incomplete = campaign.selected_types.filter(is_completed=False).exists()
        if incomplete:
            raise ValidationError("All selected campaign types must be completed (§17).")


def _campaign_created_recipients(company):
    from apps.accounts.models import User
    from django.db.models import Q
    role_codes = ["FINANCE_MANAGERS", "MARKETING_MEMBERS", "MARKETING_MANAGERS"]
    return list(User.objects.filter(
        is_active=True,
        profile__company=company
    ).filter(
        Q(profile__default_role__code__in=role_codes) |
        Q(roles__role__code__in=role_codes, roles__is_active=True)
    ).distinct())
