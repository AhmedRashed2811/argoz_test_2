"""Company tenant root + branches (docs §11, §2.3). Single active company now;
SaaS tenant root later. Holds subscription placeholders, no billing UI yet."""
from django.db import models

from apps.core.models import BaseModel


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
