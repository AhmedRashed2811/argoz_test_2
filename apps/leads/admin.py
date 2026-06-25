"""Backend admin for lead config + read-only lead inspection (docs §8, §9)."""
from django.contrib import admin

from .models import (
    BrokerLeadOwnershipHistory,
    Client,
    FollowUp,
    HowDidYouKnowOption,
    Lead,
    LeadActivity,
    LeadAssignmentHistory,
    LeadNote,
    LeadSourceDefinition,
    LeadStageDefinition,
    LeadStageHistory,
    Meeting,
    Reminder,
    SLABreachEvent,
    SLAInstance,
    WalkInQueueEntry,
)


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


@admin.register(HowDidYouKnowOption)
class HowDidYouKnowOptionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")


@admin.register(LeadAssignmentHistory)
class LeadAssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = ("lead", "to_salesman", "to_team", "assigned_at")
    list_filter = ("assigned_at",)


@admin.register(LeadStageHistory)
class LeadStageHistoryAdmin(admin.ModelAdmin):
    list_display = ("lead", "from_stage", "to_stage", "changed_at", "actor")
    list_filter = ("changed_at",)


@admin.register(SLAInstance)
class SLAInstanceAdmin(admin.ModelAdmin):
    list_display = ("lead", "stage", "deadline_at", "status")
    list_filter = ("status",)


@admin.register(SLABreachEvent)
class SLABreachEventAdmin(admin.ModelAdmin):
    list_display = ("sla_instance", "lead", "breach_type", "action_taken")


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("lead", "created_by", "status", "scheduled_at")
    list_filter = ("status",)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("lead", "created_by", "status", "scheduled_start")
    list_filter = ("status",)


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("user", "lead", "reminder_type", "due_at", "status")
    list_filter = ("status",)


@admin.register(LeadNote)
class LeadNoteAdmin(admin.ModelAdmin):
    list_display = ("lead", "created_by", "created_at")


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ("lead", "activity_type", "actor", "created_at")
    list_filter = ("activity_type",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("company", "name", "email", "phone")
    search_fields = ("name", "email", "phone")


@admin.register(WalkInQueueEntry)
class WalkInQueueEntryAdmin(admin.ModelAdmin):
    list_display = ("lead", "assigned_salesman", "status", "arrival_at")
    list_filter = ("status",)


@admin.register(BrokerLeadOwnershipHistory)
class BrokerLeadOwnershipHistoryAdmin(admin.ModelAdmin):
    list_display = ("lead", "broker", "action", "created_at")
    list_filter = ("action",)

