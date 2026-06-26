"""Lead domain (docs §8, §9, §11). Lead is mutated only through services
(§16). Broker ownership (broker_owner) is strictly separate from salesman
assignment (assigned_salesman) per §8.5."""
from django.db import models

from apps.core.models import BaseModel, CompanyOwnedModel

from .constants import ActiveStatus, AssignmentMethod, Origin, SLAStatus


class LeadSourceDefinition(BaseModel):
    """Configurable source with per-source required fields (docs §8.2)."""

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    requires_campaign = models.BooleanField(default=False)
    requires_broker = models.BooleanField(default=False)
    requires_referrer = models.BooleanField(default=False)
    requires_salesman = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


class HowDidYouKnowOption(BaseModel):
    """'How did you know us' options for Walk-in/Call Center capture (leads spec
    §4.3). 'Website' must always be present — enforced by the seed command."""

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    order_index = models.IntegerField(default=0)

    class Meta:
        ordering = ["order_index", "name"]

    def __str__(self) -> str:
        return self.name


class LeadStageDefinition(BaseModel):
    """Stage flags drive SLA/reminder/rotation behavior (docs §9.1, §9.2)."""

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    is_active_stage = models.BooleanField(default=True)
    is_terminal = models.BooleanField(default=False)
    allows_reminder = models.BooleanField(default=True)
    resets_on_rotation = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


class Lead(BaseModel, CompanyOwnedModel):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32)
    country_code = models.CharField(max_length=8, blank=True)
    email = models.EmailField(blank=True)
    source = models.ForeignKey(
        LeadSourceDefinition, on_delete=models.PROTECT, related_name="leads"
    )
    origin = models.CharField(
        max_length=10, choices=Origin.CHOICES, default=Origin.DIRECT
    )
    language = models.ForeignKey(
        "accounts.Language", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Broker ownership is separate from internal assignment (docs §8.5).
    broker_owner = models.ForeignKey(
        "accounts.Broker", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_leads",
    )
    campaign = models.ForeignKey(
        "marketing.Campaign", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="leads",
    )
    campaign_child_type = models.CharField(max_length=40, blank=True)
    campaign_child_id = models.UUIDField(null=True, blank=True)
    assigned_team = models.ForeignKey(
        "accounts.Team", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="leads",
    )
    assigned_salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_leads",
    )
    # Call Center source: the agent who captured the lead, distinct from the
    # salesman who follows up (leads spec §4.2g call-center).
    call_center_agent = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cc_agent_leads",
    )
    current_stage = models.ForeignKey(
        LeadStageDefinition, on_delete=models.PROTECT, related_name="leads",
        null=True, blank=True,
    )
    active_status = models.CharField(
        max_length=10, choices=ActiveStatus.CHOICES, default=ActiveStatus.ACTIVE
    )
    sla_deadline = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_leads",
    )
    metadata = models.JSONField(null=True, blank=True)

    @property
    def lead_timezone(self) -> str:
        COUNTRY_TIMEZONES = {
            "+20": "Africa/Cairo",      # Egypt
            "+971": "Asia/Dubai",        # UAE
            "+966": "Asia/Riyadh",       # Saudi Arabia
            "+974": "Asia/Qatar",        # Qatar
            "+965": "Asia/Kuwait",       # Kuwait
            "+973": "Asia/Bahrain",      # Bahrain
            "+968": "Asia/Muscat",       # Oman
            "+962": "Asia/Amman",        # Jordan
            "+961": "Asia/Beirut",       # Lebanon
            "+963": "Asia/Damascus",     # Syria
            "+44": "Europe/London",      # UK
            "+1": "America/New_York",    # US
            "+33": "Europe/Paris",       # France
            "+49": "Europe/Berlin",      # Germany
            "+90": "Europe/Istanbul",    # Turkey
            "+91": "Asia/Kolkata",       # India
        }
        return COUNTRY_TIMEZONES.get(self.country_code, "UTC")

    class Meta:
        indexes = [
            models.Index(fields=["company", "active_status", "assigned_salesman"]),
            models.Index(fields=["company", "phone"]),
            models.Index(fields=["company", "source"]),
            models.Index(fields=["company", "current_stage"]),
            models.Index(fields=["company", "sla_deadline"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.phone})"


class LeadAssignmentHistory(BaseModel):
    """Internal team/salesman assignment trail (docs §8.5)."""

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="assignment_history"
    )
    from_team = models.ForeignKey(
        "accounts.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    to_team = models.ForeignKey(
        "accounts.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    from_salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    to_salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assignment_method = models.CharField(max_length=30)
    strategy_code = models.CharField(max_length=40, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["lead", "assigned_at"]),
            models.Index(fields=["to_salesman", "assigned_at"]),
        ]


class LeadStageHistory(BaseModel):
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="stage_history"
    )
    from_stage = models.ForeignKey(
        LeadStageDefinition, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    to_stage = models.ForeignKey(
        LeadStageDefinition, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    sla_before = models.DateTimeField(null=True, blank=True)
    sla_after = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)


class SLAInstance(BaseModel):
    """Current and historical SLA windows (docs §11). Scanned/locked by the SLA
    job (§12.2)."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="sla_instances")
    stage = models.ForeignKey(
        LeadStageDefinition, on_delete=models.PROTECT, related_name="+"
    )
    assigned_salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    start_at = models.DateTimeField()
    deadline_at = models.DateTimeField()
    status = models.CharField(
        max_length=12, choices=SLAStatus.CHOICES, default=SLAStatus.ACTIVE
    )
    breached_at = models.DateTimeField(null=True, blank=True)
    policy_snapshot = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "deadline_at"]),
            models.Index(fields=["lead", "status"]),
        ]


class SLABreachEvent(BaseModel):
    sla_instance = models.ForeignKey(
        SLAInstance, on_delete=models.CASCADE, related_name="breach_events"
    )
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="breach_events")
    breach_type = models.CharField(max_length=40)
    handled_by_task_id = models.CharField(max_length=120, blank=True)
    action_taken = models.CharField(max_length=60, blank=True)
    metadata = models.JSONField(null=True, blank=True)


class FollowUp(BaseModel):
    """Created by FollowUpService only (docs §9.3)."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="followups")
    assigned_salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, default="SCHEDULED")
    outcome = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    completed_at = models.DateTimeField(null=True, blank=True)


class Meeting(BaseModel):
    """Created by MeetingService only (docs §9.3)."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="meetings")
    assigned_salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, default="SCHEDULED")
    outcome = models.CharField(max_length=40, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )


class Reminder(BaseModel, CompanyOwnedModel):
    """Reminders for SLA, follow-ups, meetings, frozen returns (docs §11, §12)."""

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="reminders"
    )
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, null=True, blank=True, related_name="reminders"
    )
    related_type = models.CharField(max_length=40, blank=True)
    related_id = models.UUIDField(null=True, blank=True)
    reminder_type = models.CharField(max_length=40)
    due_at = models.DateTimeField()
    status = models.CharField(max_length=20, default="PENDING")
    sent_at = models.DateTimeField(null=True, blank=True)
    channel = models.CharField(max_length=20, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "due_at"])]


class LeadNote(BaseModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="lead_notes")
    body = models.TextField()
    visibility = models.CharField(max_length=20, default="INTERNAL")
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    is_deleted = models.BooleanField(default=False)


class LeadActivity(BaseModel):
    """Calls, messages, emails, attempts, updates (docs §11)."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=40)
    body = models.TextField(blank=True)
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    metadata = models.JSONField(null=True, blank=True)


class Client(BaseModel, CompanyOwnedModel):
    """Existing client relationship (docs §11, §8.2 existing-client policy)."""

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32)
    email = models.EmailField(blank=True)
    original_salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_from_lead = models.ForeignKey(
        Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=20, default="ACTIVE")


class WalkInQueueEntry(BaseModel):
    """Walk-in reception queue (docs §8.2 walk-in policy)."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="walkin_entries")
    arrival_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="WAITING")
    selected_policy_code = models.CharField(max_length=40, blank=True)
    assigned_salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    receptionist = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )


class BrokerLeadOwnershipHistory(BaseModel):
    """Broker ownership changes, separate table from salesman assignment (§8.5)."""

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="broker_ownership_history"
    )
    broker = models.ForeignKey(
        "accounts.Broker", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    action = models.CharField(max_length=30)
    old_broker = models.ForeignKey(
        "accounts.Broker", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    new_broker = models.ForeignKey(
        "accounts.Broker", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reason = models.TextField(blank=True)
