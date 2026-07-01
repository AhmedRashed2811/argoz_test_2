from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "db_name", "is_active", "paid_until", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "db_name")
    readonly_fields = ("db_name", "created_at", "updated_at")
