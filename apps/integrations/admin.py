from django.contrib import admin

from .models import (
    IntegrationProvider,
    WebhookEndpoint,
    WebhookEvent,
    WebhookMapping,
)


class MappingInline(admin.TabularInline):
    model = WebhookMapping
    extra = 0


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "provider", "endpoint_uuid", "status",
                    "last_used_at")
    readonly_fields = ("endpoint_uuid",)
    inlines = [MappingInline]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("endpoint", "status", "received_at", "processed_at")
    list_filter = ("status",)
    readonly_fields = ("payload", "dedupe_hash", "external_event_id")


admin.site.register(IntegrationProvider)
