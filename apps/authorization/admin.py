"""Backend admin for roles/permissions (docs §4) until the UI matrix is built."""
from django.contrib import admin

from .models import (
    PageDefinition,
    PermissionDefinition,
    RoleGroup,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)


@admin.register(PermissionDefinition)
class PermissionDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "module", "action", "risk_level", "is_active")
    search_fields = ("code", "name")
    list_filter = ("module", "risk_level")


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0
    raw_id_fields = ("permission",)


@admin.register(RoleGroup)
class RoleGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "company", "is_system_default", "is_active")
    inlines = [RolePermissionInline]


admin.site.register(PageDefinition)
admin.site.register(UserRole)
admin.site.register(UserPermissionOverride)
