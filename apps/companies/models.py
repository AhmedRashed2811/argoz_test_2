"""Company tenant root + branches (docs §11, §2.3). Single active company now;
SaaS tenant root later. Holds subscription placeholders, no billing UI yet."""
import secrets

from django.db import models

from apps.core.models import BaseModel


def generate_api_key() -> str:
    """Bearer/x-api-key token for the external leads API. URL-safe, ~43 chars."""
    return secrets.token_urlsafe(32)


class SubscriptionStatus:
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    CHOICES = [
        (ACTIVE, "Active"),
        (SUSPENDED, "Suspended"),
        (CANCELLED, "Cancelled"),
    ]


class Company(BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    # Placeholders managed later by the planned SaaS app (docs §2.3).
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.CHOICES,
        default=SubscriptionStatus.ACTIVE,
    )
    plan_code = models.CharField(max_length=50, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    # Auth token for the external read-only leads API (Bearer / x-api-key).
    api_key = models.CharField(
        max_length=64, unique=True, default=generate_api_key,
        help_text="Token external systems send to read this company's leads.",
    )

    class Meta:
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return self.name


class Branch(BaseModel):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="branches"
    )
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "branches"

    def __str__(self) -> str:
        return self.name
