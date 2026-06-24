"""Finance approval façade (docs §3: finance owns approval screens, not campaign
creation). Delegates the write to CampaignApprovalService so budget rules and
audit stay centralized in marketing."""
from __future__ import annotations

from apps.marketing.constants import ApprovalStatus
from apps.marketing.services import CampaignApprovalService


class FinanceApprovalService:
    @staticmethod
    def approve(*, campaign_id, actor, reason="", request_meta=None):
        return CampaignApprovalService.set_status(
            campaign_id=campaign_id, status=ApprovalStatus.APPROVED, actor=actor,
            reason=reason, request_meta=request_meta,
        )

    @staticmethod
    def semi_approve(*, campaign_id, actor, reason, request_meta=None):
        return CampaignApprovalService.set_status(
            campaign_id=campaign_id, status=ApprovalStatus.SEMI_APPROVED, actor=actor,
            reason=reason, request_meta=request_meta,
        )

    @staticmethod
    def reject(*, campaign_id, actor, reason, request_meta=None):
        return CampaignApprovalService.set_status(
            campaign_id=campaign_id, status=ApprovalStatus.NOT_APPROVED, actor=actor,
            reason=reason, request_meta=request_meta,
        )
