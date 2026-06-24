"""Tenant-specific dynamic webhooks (docs §13). Each company gets its own
endpoint UUID + secret; inbound payloads are stored/audited before processing,
deduplicated, mapped, then funneled through LeadCreationService."""
import uuid

from django.db import models

from apps.core.models import BaseModel, CompanyOwnedModel


class IntegrationProvider(BaseModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


class WebhookEndpoint(BaseModel, CompanyOwnedModel):
    """Self-service per-company endpoint (docs §13.2)."""

    provider = models.ForeignKey(
        IntegrationProvider, on_delete=models.PROTECT, related_name="endpoints"
    )
    name = models.CharField(max_length=120)
    endpoint_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    secret_token = models.CharField(max_length=128)
    status = models.CharField(max_length=20, default="ACTIVE")
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    # Attribution defaults applied to leads created from this endpoint.
    default_source_code = models.CharField(max_length=40, default="CAMPAIGN")
    default_campaign = models.ForeignKey(
        "marketing.Campaign", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="webhook_endpoints",
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.endpoint_uuid})"


class WebhookMapping(BaseModel):
    """Maps external payload fields to CRM lead fields (docs §13.2). Required
    targets: name, phone."""

    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="mappings"
    )
    source_field = models.CharField(max_length=120)
    target_field = models.CharField(max_length=60)
    transform_rule = models.JSONField(null=True, blank=True)
    required = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["endpoint", "target_field"], name="uniq_endpoint_target_field"
            )
        ]


class WebhookEvent(BaseModel):
    """Inbound event with idempotency keys (docs §13.2, §17)."""

    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="events"
    )
    external_event_id = models.CharField(max_length=200, blank=True)
    payload = models.JSONField()
    status = models.CharField(max_length=20, default="RECEIVED")
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    dedupe_hash = models.CharField(max_length=64, blank=True)
    created_lead = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["endpoint", "external_event_id"],
                condition=~models.Q(external_event_id=""),
                name="uniq_endpoint_external_event_id",
            ),
            models.UniqueConstraint(
                fields=["endpoint", "dedupe_hash"],
                condition=~models.Q(dedupe_hash=""),
                name="uniq_endpoint_dedupe_hash",
            ),
        ]
        indexes = [models.Index(fields=["status", "received_at"])]


class WebhookRetry(BaseModel):
    webhook_event = models.ForeignKey(
        WebhookEvent, on_delete=models.CASCADE, related_name="retries"
    )
    attempt_number = models.IntegerField(default=1)
    status = models.CharField(max_length=20, default="PENDING")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
