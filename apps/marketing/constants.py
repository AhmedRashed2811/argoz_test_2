"""Marketing stable codes (docs §10). Lifecycle is date-derived; finance
approval is a separate persisted status."""


class CampaignType:
    EVENTS = "EVENTS"
    TV_ADS = "TV_ADS"
    STREET_ADS = "STREET_ADS"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    EXHIBITION = "EXHIBITION"
    ALL = [EVENTS, TV_ADS, STREET_ADS, SOCIAL_MEDIA, EXHIBITION]


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
