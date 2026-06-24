"""Stable lead-domain codes (docs §8, §9). Stage/source codes are immutable
internal system identifiers; behavior per code is configured via policies."""


class StageCode:
    FRESH = "FRESH"
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    FOLLOW_UP = "FOLLOW_UP"
    MEETING = "MEETING"
    NOT_REACHED = "NOT_REACHED"
    FROZEN = "FROZEN"
    ALL = [FRESH, INTERESTED, NOT_INTERESTED, FOLLOW_UP, MEETING, NOT_REACHED, FROZEN]


class SourceCode:
    SELF_GENERATED = "SELF_GENERATED"
    CAMPAIGN = "CAMPAIGN"
    BROKER = "BROKER"
    WALK_IN = "WALK_IN"
    CALL_CENTER = "CALL_CENTER"
    EXHIBITION = "EXHIBITION"
    REFERRAL = "REFERRAL"
    EXISTING_CLIENT = "EXISTING_CLIENT"
    ALL = [
        SELF_GENERATED, CAMPAIGN, BROKER, WALK_IN, CALL_CENTER,
        EXHIBITION, REFERRAL, EXISTING_CLIENT,
    ]


class Origin:
    DIRECT = "DIRECT"
    BROKER = "BROKER"
    CHOICES = [(DIRECT, "Direct"), (BROKER, "Broker/Indirect")]


class ActiveStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    CHOICES = [(ACTIVE, "Active"), (INACTIVE, "Inactive")]


class SLAStatus:
    ACTIVE = "ACTIVE"
    BREACHED = "BREACHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    CHOICES = [
        (ACTIVE, "Active"),
        (BREACHED, "Breached"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
    ]


class AssignmentMethod:
    MANUAL = "MANUAL"
    AUTO = "AUTO"
    SLA_ROTATION = "SLA_ROTATION"
    RETRY = "RETRY"
    ESCALATION = "ESCALATION"


class ScopeMode:
    TEAM_THEN_SALESMAN = "TEAM_THEN_SALESMAN"
    TEAM_HEAD_DECIDES = "TEAM_HEAD_DECIDES"
    ALL_SALESMEN = "ALL_SALESMEN"


class SLAExpiryMethod:
    ROUND_ROBIN = "ROUND_ROBIN"
    RETRY_TEAM_ESCALATION = "RETRY_TEAM_ESCALATION"
    MANUAL = "MANUAL"
