"""Lead -> campaign attribution (docs §10.5). Stores campaign and, where known,
the child source (event/platform). For social ads linked to events, both
social_ad and event are traceable."""
from __future__ import annotations

from ..models import CampaignLeadAttribution


class CampaignAttributionService:
    @staticmethod
    def link_lead(*, lead, platform=None, event=None, source_type="", source_id=None):
        if lead.campaign_id is None:
            return None
        return CampaignLeadAttribution.objects.create(
            campaign_id=lead.campaign_id,
            lead=lead,
            source_type=source_type or lead.campaign_child_type,
            source_id=source_id or lead.campaign_child_id,
            platform=platform,
            event=event,
        )
