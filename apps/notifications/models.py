"""Typed notification system (docs §11, §12.3). Created by business events via
NotificationService, never ad-hoc in views. Delivery tracked per channel."""
from django.db import models

from apps.core.models import BaseModel, CompanyOwnedModel


class NotificationType(BaseModel):
    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=150)
    default_channels = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


class Notification(BaseModel, CompanyOwnedModel):
    recipient = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.ForeignKey(
        NotificationType, on_delete=models.PROTECT, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    priority = models.CharField(max_length=20, default="NORMAL")
    related_type = models.CharField(max_length=40, blank=True)
    related_id = models.CharField(max_length=64, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["recipient", "is_read", "created_at"])]


class NotificationDelivery(BaseModel):
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="deliveries"
    )
    channel = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default="PENDING")
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)


class EmailTemplate(BaseModel, CompanyOwnedModel):
    code = models.CharField(max_length=60)
    subject_template = models.CharField(max_length=255)
    body_template = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uniq_company_email_template"
            )
        ]


class EmailOutbox(BaseModel, CompanyOwnedModel):
    """Outbox pattern for reliable async email (docs §16, §12)."""

    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, default="PENDING")
    attempts = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    send_after = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "send_after"])]
