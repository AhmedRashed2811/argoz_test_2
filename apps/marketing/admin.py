from django.contrib import admin

from .models import (
    Campaign,
    CampaignApprovalHistory,
    CampaignAsset,
    CampaignBudgetSnapshot,
    CampaignLeadAttribution,
    CampaignSelectedType,
    EventAttendee,
    EventCatering,
    EventCelebrity,
    EventGiveaway,
    EventRecord,
    ExhibitionRecord,
    OtherCost,
    Project,
    SocialMediaAdRecord,
    SocialMediaPlatformLine,
    SocialPlatformDefinition,
    StreetAdLocation,
    StreetAdRecord,
    StreetAdTypeDefinition,
    StreetAdTypeLine,
    TVAdRecord,
    TVChannel,
    TVSlot,
    Unit,
)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "start_date", "end_date", "approval_status",
                    "total_budget")
    list_filter = ("approval_status",)
    search_fields = ("name",)
    # total_budget is computed by CampaignBudgetService (docs §10.4).
    readonly_fields = ("total_budget",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("company", "name", "status")
    search_fields = ("name",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("project", "unit_code", "status", "price")
    list_filter = ("status",)


@admin.register(CampaignSelectedType)
class CampaignSelectedTypeAdmin(admin.ModelAdmin):
    list_display = ("campaign", "type_code")


@admin.register(CampaignAsset)
class CampaignAssetAdmin(admin.ModelAdmin):
    list_display = ("campaign", "file", "asset_type")


@admin.register(EventRecord)
class EventRecordAdmin(admin.ModelAdmin):
    list_display = ("campaign", "name", "venue", "event_date")


@admin.register(EventCelebrity)
class EventCelebrityAdmin(admin.ModelAdmin):
    list_display = ("event", "name", "budget")


@admin.register(EventGiveaway)
class EventGiveawayAdmin(admin.ModelAdmin):
    list_display = ("event", "name", "budget")


@admin.register(EventCatering)
class EventCateringAdmin(admin.ModelAdmin):
    list_display = ("event", "name", "budget")


@admin.register(TVAdRecord)
class TVAdRecordAdmin(admin.ModelAdmin):
    list_display = ("campaign", "name", "budget")


@admin.register(TVChannel)
class TVChannelAdmin(admin.ModelAdmin):
    list_display = ("tv_ad", "channel_name", "budget")


@admin.register(TVSlot)
class TVSlotAdmin(admin.ModelAdmin):
    list_display = ("tv_ad", "appearance_time", "number_of_appearances")


@admin.register(StreetAdRecord)
class StreetAdRecordAdmin(admin.ModelAdmin):
    list_display = ("campaign", "name", "budget")


@admin.register(StreetAdTypeLine)
class StreetAdTypeLineAdmin(admin.ModelAdmin):
    list_display = ("street_ad", "ad_type", "budget")


@admin.register(StreetAdLocation)
class StreetAdLocationAdmin(admin.ModelAdmin):
    list_display = ("type_line", "location_text", "budget")


@admin.register(ExhibitionRecord)
class ExhibitionRecordAdmin(admin.ModelAdmin):
    list_display = ("campaign", "name", "budget")


@admin.register(SocialMediaAdRecord)
class SocialMediaAdRecordAdmin(admin.ModelAdmin):
    list_display = ("campaign", "name")


@admin.register(SocialMediaPlatformLine)
class SocialMediaPlatformLineAdmin(admin.ModelAdmin):
    list_display = ("social_ad", "platform", "budget")


@admin.register(OtherCost)
class OtherCostAdmin(admin.ModelAdmin):
    list_display = ("campaign", "value", "created_by")


@admin.register(CampaignApprovalHistory)
class CampaignApprovalHistoryAdmin(admin.ModelAdmin):
    list_display = ("campaign", "to_status", "created_at", "actor")


@admin.register(CampaignLeadAttribution)
class CampaignLeadAttributionAdmin(admin.ModelAdmin):
    list_display = ("campaign", "lead", "created_at")


@admin.register(EventAttendee)
class EventAttendeeAdmin(admin.ModelAdmin):
    list_display = ("event", "name", "phone")


@admin.register(CampaignBudgetSnapshot)
class CampaignBudgetSnapshotAdmin(admin.ModelAdmin):
    list_display = ("campaign", "total_budget", "created_at")


admin.site.register(SocialPlatformDefinition)
admin.site.register(StreetAdTypeDefinition)
