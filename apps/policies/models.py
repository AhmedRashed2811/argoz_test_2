"""Configurable policy storage (docs §7.1). Data-driven so business edits rules
without code changes. Services resolve values via PolicyResolver, never hardcode."""
from django.db import models

from apps.core.models import BaseModel, CompanyOwnedModel

from .constants import ValueType


class PolicyDefinition(BaseModel):
    code = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=150)
    module = models.CharField(max_length=60)
    description = models.TextField(blank=True)
    value_type = models.CharField(
        max_length=20, choices=ValueType.CHOICES, default=ValueType.OPTION
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


class PolicyOptionDefinition(BaseModel):
    """Allowed choice; strategy_code links an option to an OOP strategy class
    (docs §7.1, §16) e.g. ROUND_ROBIN -> RoundRobinStrategy."""

    policy = models.ForeignKey(
        PolicyDefinition, on_delete=models.CASCADE, related_name="options"
    )
    code = models.CharField(max_length=80)
    label = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    strategy_code = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["policy", "code"], name="uniq_policy_option_code"
            )
        ]

    def __str__(self) -> str:
        return f"{self.policy.code}:{self.code}"


class CompanyPolicyValue(BaseModel, CompanyOwnedModel):
    """Selected policy value for the company (docs §7.1)."""

    policy = models.ForeignKey(
        PolicyDefinition, on_delete=models.CASCADE, related_name="company_values"
    )
    selected_option = models.ForeignKey(
        PolicyOptionDefinition, on_delete=models.SET_NULL, null=True, blank=True
    )
    value_json = models.JSONField(null=True, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "policy"], name="uniq_company_policy"
            )
        ]


class PolicyParameter(BaseModel):
    """Parameters like SLA hours, retry n, rotation order (docs §7.1)."""

    company_policy = models.ForeignKey(
        CompanyPolicyValue, on_delete=models.CASCADE, related_name="parameters"
    )
    key = models.CharField(max_length=80)
    value_type = models.CharField(
        max_length=20, choices=ValueType.CHOICES, default=ValueType.JSON
    )
    value_json = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company_policy", "key"], name="uniq_policy_parameter"
            )
        ]


class StrategyDefinition(BaseModel):
    """Maps a DB strategy code to an importable OOP class (docs §11, §16).
    The registry prefers this table, falling back to the static safe registry."""

    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=150)
    class_path = models.CharField(max_length=255)
    module = models.CharField(max_length=60, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(null=True, blank=True)

    def __str__(self) -> str:
        return self.code
