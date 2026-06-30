"""Marketing campaign master + type children (docs §10, §11). Budgets are
DecimalField with non-negative DB constraints (§10.4, §17); heavy creation lives
in services, never views (§10.3)."""
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.core.models import BaseModel, CompanyOwnedModel

from .constants import ApprovalStatus

MONEY = dict(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])


def _budget_constraint(name):
    return models.CheckConstraint(check=models.Q(budget__gte=0), name=name)


# --- Campaign targets (docs §10.1) ---
class Project(BaseModel, CompanyOwnedModel):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    developer = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=30, blank=True)
    metadata = models.JSONField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class Unit(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="units")
    unit_code = models.CharField(max_length=60)
    unit_type = models.CharField(max_length=60, blank=True)
    area = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=30, blank=True)


class Campaign(BaseModel, CompanyOwnedModel):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    target_type = models.CharField(max_length=30, blank=True)
    target_id = models.UUIDField(null=True, blank=True)
    approval_status = models.CharField(
        max_length=20, choices=ApprovalStatus.CHOICES, default=ApprovalStatus.PENDING
    )
    approval_reason = models.TextField(blank=True)
    total_budget = models.DecimalField(default=0, **MONEY)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    rejected_budgets = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="campaign_end_after_start",
            ),
            models.CheckConstraint(
                check=models.Q(total_budget__gte=0), name="campaign_budget_non_negative"
            ),
        ]
        indexes = [
            models.Index(fields=["company", "start_date", "end_date"]),
            models.Index(fields=["company", "approval_status"]),
            models.Index(fields=["company", "archived_at"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def lifecycle_status(self) -> str:
        """Date-derived Coming/Active/Ended (docs marketing §5.2). Separate from
        the persisted approval_status."""
        from django.utils import timezone

        from .constants import LifecycleStatus

        today = timezone.now().date()
        if today < self.start_date:
            return LifecycleStatus.COMING
        if today > self.end_date:
            return LifecycleStatus.ENDED
        return LifecycleStatus.ACTIVE


class CampaignSelectedType(BaseModel):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="selected_types"
    )
    type_code = models.CharField(max_length=30)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "type_code"], name="uniq_campaign_type"
            )
        ]


class CampaignAsset(BaseModel):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="assets"
    )
    related_type = models.CharField(max_length=40, blank=True)
    related_id = models.UUIDField(null=True, blank=True)
    file = models.FileField(upload_to="campaign_assets/")
    asset_type = models.CharField(max_length=20, default="IMAGE")
    uploaded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)


# --- Events ---
class EventRecord(BaseModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="events")
    name = models.CharField(max_length=200)
    venue = models.CharField(max_length=200, blank=True)
    event_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(default=0, **MONEY)
    description = models.TextField(blank=True)
    logo = models.ForeignKey(
        CampaignAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    target_attendees = models.PositiveIntegerField(default=0)
    # Real headcount of people who actually attended. Entered/edited only AFTER
    # the event row exists (never at campaign creation); always editable
    # regardless of approval. null = not yet recorded.
    actual_attendees = models.PositiveIntegerField(null=True, blank=True)
    lead_count = models.PositiveIntegerField(default=0)  # ROI denormalization (§10.5)

    class Meta:
        constraints = [_budget_constraint("event_budget_non_negative")]


class EventCelebrity(BaseModel):
    event = models.ForeignKey(
        EventRecord, on_delete=models.CASCADE, related_name="celebrities"
    )
    name = models.CharField(max_length=200)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


class EventGiveaway(BaseModel):
    event = models.ForeignKey(
        EventRecord, on_delete=models.CASCADE, related_name="giveaways"
    )
    name = models.CharField(max_length=200)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


class EventCatering(BaseModel):
    event = models.ForeignKey(
        EventRecord, on_delete=models.CASCADE, related_name="catering"
    )
    name = models.CharField(max_length=200)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


class EventPrintOut(BaseModel):
    """Print-out line for an event (task 2) — mirrors celebrities/giveaways."""

    event = models.ForeignKey(
        EventRecord, on_delete=models.CASCADE, related_name="printouts"
    )
    name = models.CharField(max_length=200)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


# --- TV Ads ---
class TVAdRecord(BaseModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="tv_ads")
    name = models.CharField(max_length=200)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(default=0, **MONEY)
    description = models.TextField(blank=True)
    lead_count = models.PositiveIntegerField(default=0)  # ROI denormalization (§10.5)


class TVChannel(BaseModel):
    tv_ad = models.ForeignKey(TVAdRecord, on_delete=models.CASCADE, related_name="channels")
    channel_name = models.CharField(max_length=120)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


class TVSlot(BaseModel):
    tv_ad = models.ForeignKey(TVAdRecord, on_delete=models.CASCADE, related_name="slots")
    appearance_time = models.TimeField(null=True, blank=True)
    number_of_appearances = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)


# --- Street Ads ---
class StreetAdRecord(BaseModel):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="street_ads"
    )
    name = models.CharField(max_length=200)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(default=0, **MONEY)
    description = models.TextField(blank=True)
    lead_count = models.PositiveIntegerField(default=0)  # ROI denormalization (§10.5)


class StreetAdTypeDefinition(BaseModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    requires_exact_location = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


class StreetAdTypeLine(BaseModel):
    street_ad = models.ForeignKey(
        StreetAdRecord, on_delete=models.CASCADE, related_name="type_lines"
    )
    ad_type = models.ForeignKey(
        StreetAdTypeDefinition, on_delete=models.PROTECT, related_name="+"
    )
    total_number = models.PositiveIntegerField(default=1)
    budget = models.DecimalField(default=0, **MONEY)
    description = models.TextField(blank=True)


class StreetAdLocation(BaseModel):
    type_line = models.ForeignKey(
        StreetAdTypeLine, on_delete=models.CASCADE, related_name="locations"
    )
    location_text = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


# --- Exhibition ---
class ExhibitionRecord(BaseModel):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="exhibitions"
    )
    name = models.CharField(max_length=200)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(default=0, **MONEY)
    place = models.CharField(max_length=200, blank=True)
    lead_count = models.PositiveIntegerField(default=0)  # ROI denormalization (§10.5)


# Exhibition sub-sections (task 3) — same shape as the event ones.
class ExhibitionCelebrity(BaseModel):
    exhibition = models.ForeignKey(
        ExhibitionRecord, on_delete=models.CASCADE, related_name="celebrities"
    )
    name = models.CharField(max_length=200)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


class ExhibitionGiveaway(BaseModel):
    exhibition = models.ForeignKey(
        ExhibitionRecord, on_delete=models.CASCADE, related_name="giveaways"
    )
    name = models.CharField(max_length=200)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


class ExhibitionCatering(BaseModel):
    exhibition = models.ForeignKey(
        ExhibitionRecord, on_delete=models.CASCADE, related_name="catering"
    )
    name = models.CharField(max_length=200)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


class ExhibitionPrintOut(BaseModel):
    exhibition = models.ForeignKey(
        ExhibitionRecord, on_delete=models.CASCADE, related_name="printouts"
    )
    name = models.CharField(max_length=200)
    budget = models.DecimalField(default=0, **MONEY)
    notes = models.TextField(blank=True)


# --- Social Media ---
class SocialPlatformDefinition(BaseModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    supports_webhook = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.code


class SocialMediaAdRecord(BaseModel):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="social_ads"
    )
    name = models.CharField(max_length=200)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    target_kpi = models.CharField(max_length=120, blank=True)
    linked_event = models.ForeignKey(
        EventRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    description = models.TextField(blank=True)
    lead_count = models.PositiveIntegerField(default=0)  # ROI denormalization (§10.5)


class SocialMediaPlatformLine(BaseModel):
    social_ad = models.ForeignKey(
        SocialMediaAdRecord, on_delete=models.CASCADE, related_name="platform_lines"
    )
    platform = models.ForeignKey(
        SocialPlatformDefinition, on_delete=models.PROTECT, related_name="+"
    )
    budget = models.DecimalField(default=0, **MONEY)
    target_kpi_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    creatives = models.JSONField(null=True, blank=True)
    external_campaign_id = models.CharField(max_length=120, blank=True)


# --- Other costs / finance / attribution (docs §10.4, §10.5) ---
class OtherCost(BaseModel):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="other_costs"
    )
    value = models.DecimalField(default=0, **MONEY)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(value__gte=0), name="other_cost_non_negative"
            )
        ]


class CampaignApprovalHistory(BaseModel):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="approval_history"
    )
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    reason = models.TextField(blank=True)
    budget_snapshot = models.JSONField(null=True, blank=True)
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )


class CampaignLeadAttribution(BaseModel):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="lead_attributions"
    )
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.CASCADE, related_name="campaign_attributions"
    )
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.UUIDField(null=True, blank=True)
    platform = models.ForeignKey(
        SocialPlatformDefinition, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    event = models.ForeignKey(
        EventRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        indexes = [
            models.Index(fields=["campaign", "lead"]),
            models.Index(fields=["campaign", "source_type", "source_id"]),
        ]


class EventAttendee(BaseModel):
    event = models.ForeignKey(
        EventRecord, on_delete=models.CASCADE, related_name="attendees"
    )
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    source_type = models.CharField(max_length=40, blank=True)
    social_ad = models.ForeignKey(
        SocialMediaAdRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)


@receiver(post_delete, sender="marketing.CampaignAsset")
def _delete_campaign_asset_file(sender, instance, **kwargs):
    """Remove the file from storage when its row is deleted — covers child
    rebuild on edit and the cascade when a campaign is deleted."""
    if instance.file:
        instance.file.delete(save=False)


class CampaignBudgetSnapshot(BaseModel):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="budget_snapshots"
    )
    total_budget = models.DecimalField(default=0, **MONEY)
    breakdown_json = models.JSONField(null=True, blank=True)
    calculated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    calculated_at = models.DateTimeField(auto_now_add=True)
