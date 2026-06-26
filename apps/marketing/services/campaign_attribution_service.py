"""Lead -> campaign attribution (docs §10.5). Stores campaign and, where known,
the child source (event/platform). For social ads linked to events, both
social_ad and event are traceable. Also keeps the denormalized per-channel
lead_count counters in sync for ROI/marketing reporting (§10.5)."""
from __future__ import annotations

from django.db.models import F

from ..constants import ChannelType
from ..models import (
    CampaignLeadAttribution,
    EventRecord,
    ExhibitionRecord,
    SocialMediaAdRecord,
    StreetAdRecord,
    TVAdRecord,
)

# Maps a Lead.campaign_child_type code to the child model whose lead_count is bumped.
_CHILD_MODEL = {
    ChannelType.EVENT: EventRecord,
    ChannelType.TV_AD: TVAdRecord,
    ChannelType.STREET_AD: StreetAdRecord,
    ChannelType.SOCIAL_MEDIA_AD: SocialMediaAdRecord,
    ChannelType.EXHIBITION: ExhibitionRecord,
}


class CampaignAttributionService:
    @staticmethod
    def link_lead(*, lead, platform=None, event=None, source_type="", source_id=None):
        if lead.campaign_id is None:
            return None
        source_type = source_type or lead.campaign_child_type
        source_id = source_id or lead.campaign_child_id
        attribution = CampaignLeadAttribution.objects.create(
            campaign_id=lead.campaign_id,
            lead=lead,
            source_type=source_type,
            source_id=source_id,
            platform=platform,
            event=event,
        )
        CampaignAttributionService._bump_counts(source_type, source_id)
        return attribution

    @staticmethod
    def _bump_counts(source_type, source_id):
        """Atomic F() increment of the matching channel's lead_count. Campaign's
        own count stays derived via Count(lead_attributions) in selectors."""
        model = _CHILD_MODEL.get(source_type)
        if model is None or source_id is None:
            return
        model.objects.filter(pk=source_id).update(lead_count=F("lead_count") + 1)
