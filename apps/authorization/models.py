"""Custom CRM authorization (docs §4, §5). Roles are default permission
bundles; users union role defaults + direct ALLOW and minus direct DENY.
Page + action permissions, UI-manageable, never role-name if/else (§3, §4.2)."""
from django.db import models

from apps.core.models import BaseModel, CompanyOwnedModel


class RiskLevel:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CHOICES = [(LOW, "Low"), (MEDIUM, "Medium"), (HIGH, "High")]


class Effect:
    ALLOW = "ALLOW"
    DENY = "DENY"
    CHOICES = [(ALLOW, "Allow"), (DENY, "Deny")]


class RoleGroup(BaseModel, CompanyOwnedModel):
    """Business role/group = default permission template (docs §4.2)."""

    code = models.CharField(max_length=80)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_system_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uniq_company_role_code"
            )
        ]

    def __str__(self) -> str:
        return self.name


class PageDefinition(BaseModel):
    """Controls page/menu/tab access (docs §4.4). Self-parent builds the menu
    tree; permissions reference pages for page-access checks."""

    code = models.CharField(max_length=120, unique=True)
    module = models.CharField(max_length=60)
    name = models.CharField(max_length=120)
    url_name = models.CharField(max_length=120, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    icon = models.CharField(max_length=60, blank=True)
    menu_order = models.IntegerField(default=0)
    is_menu_item = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["module", "menu_order"]

    def __str__(self) -> str:
        return self.code


class PermissionDefinition(BaseModel):
    """A business action or page ability with a stable code (docs §4.2, §5.1)
    such as leads.lead.assign_manual. Created/managed from the UI catalog."""

    code = models.CharField(max_length=150, unique=True)
    module = models.CharField(max_length=60)
    page = models.ForeignKey(
        PageDefinition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="permissions",
    )
    action = models.CharField(max_length=80)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    risk_level = models.CharField(
        max_length=10, choices=RiskLevel.CHOICES, default=RiskLevel.LOW
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


class UserRole(BaseModel):
    """Users can hold one or more active roles (docs §4.3 step 1)."""

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="roles"
    )
    role = models.ForeignKey(
        RoleGroup, on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="role_grants",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uniq_user_role")
        ]


class RolePermission(BaseModel):
    """Default permission bundle per role (docs §11). allow=False lets a role
    template explicitly carve out a default."""

    role = models.ForeignKey(
        RoleGroup, on_delete=models.CASCADE, related_name="permissions"
    )
    permission = models.ForeignKey(
        PermissionDefinition, on_delete=models.CASCADE, related_name="role_links"
    )
    allow = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="uniq_role_permission"
            )
        ]


class UserPermissionOverride(BaseModel):
    """Direct per-user customization; DENY wins over role defaults (docs §4.3)."""

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="permission_overrides"
    )
    permission = models.ForeignKey(
        PermissionDefinition, on_delete=models.CASCADE, related_name="overrides"
    )
    effect = models.CharField(max_length=10, choices=Effect.CHOICES)
    reason = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="override_grants",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "permission", "effect"],
                name="uniq_user_permission_effect",
            )
        ]
