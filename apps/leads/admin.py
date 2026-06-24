"""Backend admin for lead config + read-only lead inspection (docs §8, §9)."""
from django.contrib import admin

from .models import Lead, LeadSourceDefinition, LeadStageDefinition


@admin.register(LeadStageDefinition)
class LeadStageDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active_stage", "is_terminal", "resets_on_rotation")


@admin.register(LeadSourceDefinition)
class LeadSourceDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "requires_campaign", "requires_broker",
                    "requires_salesman")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "source", "current_stage", "assigned_salesman",
                    "active_status", "sla_deadline")
    list_filter = ("active_status", "origin", "source")
    search_fields = ("name", "phone", "email")
    raw_id_fields = ("assigned_salesman", "assigned_team", "broker_owner", "campaign")
    # Leads must be mutated through services, not the admin form (docs §16).
    readonly_fields = ("current_stage", "sla_deadline", "active_status")
