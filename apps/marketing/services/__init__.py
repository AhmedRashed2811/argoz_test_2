"""Marketing service layer (docs §10.3)."""
from .campaign_approval_service import CampaignApprovalService
from .campaign_attribution_service import CampaignAttributionService
from .campaign_budget_service import CampaignBudgetService
from .campaign_creation_service import CampaignCreationService
from .campaign_payload_service import CampaignPayloadService
from .campaign_roi_service import CampaignROIService

__all__ = [
    "CampaignApprovalService",
    "CampaignAttributionService",
    "CampaignBudgetService",
    "CampaignCreationService",
    "CampaignPayloadService",
    "CampaignROIService",
]
