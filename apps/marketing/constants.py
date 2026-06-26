"""Marketing stable codes (docs §10). Lifecycle is date-derived; finance
approval is a separate persisted status."""


class CampaignType:
    EVENTS = "EVENTS"
    TV_ADS = "TV_ADS"
    STREET_ADS = "STREET_ADS"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    EXHIBITION = "EXHIBITION"
    ALL = [EVENTS, TV_ADS, STREET_ADS, SOCIAL_MEDIA, EXHIBITION]


class ChannelType:
    """Campaign child kind stored on Lead.campaign_child_type / attribution
    source_type. Used to route lead-count increments (docs §10.5)."""

    EVENT = "EVENT"
    TV_AD = "TV_AD"
    STREET_AD = "STREET_AD"
    SOCIAL_MEDIA_AD = "SOCIAL_MEDIA_AD"
    EXHIBITION = "EXHIBITION"
    ALL = [EVENT, TV_AD, STREET_AD, SOCIAL_MEDIA_AD, EXHIBITION]


# Frontend channel value <-> ChannelType code <-> CampaignType (selected_types).
FE_TO_CHANNEL = {
    "event": ChannelType.EVENT,
    "tv_ad": ChannelType.TV_AD,
    "street_ad": ChannelType.STREET_AD,
    "social_media_ad": ChannelType.SOCIAL_MEDIA_AD,
    "exhibition": ChannelType.EXHIBITION,
}
CHANNEL_TO_FE = {v: k for k, v in FE_TO_CHANNEL.items()}
CHANNEL_LABELS = {
    "event": "Event", "tv_ad": "TV Ad", "street_ad": "Street Ad",
    "social_media_ad": "Social Media Ad", "exhibition": "Exhibition",
}
# Campaign.selected_types.type_code (CampaignType) -> frontend channel value.
CAMPAIGNTYPE_TO_FE = {
    "EVENTS": "event", "TV_ADS": "tv_ad", "STREET_ADS": "street_ad",
    "SOCIAL_MEDIA": "social_media_ad", "EXHIBITION": "exhibition",
}


class ApprovalStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    SEMI_APPROVED = "SEMI_APPROVED"
    NOT_APPROVED = "NOT_APPROVED"
    CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (SEMI_APPROVED, "Semi Approved"),
        (NOT_APPROVED, "Not Approved"),
    ]
    # Reason mandatory for these (docs §10.4).
    REASON_REQUIRED = {SEMI_APPROVED, NOT_APPROVED}


class LifecycleStatus:
    COMING = "COMING"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
