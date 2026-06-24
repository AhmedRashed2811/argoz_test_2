from django.contrib import admin

from .models import (
    Campaign,
    SocialPlatformDefinition,
    StreetAdTypeDefinition,
)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "start_date", "end_date", "approval_status",
                    "total_budget")
    list_filter = ("approval_status",)
    search_fields = ("name",)
    # total_budget is computed by CampaignBudgetService (docs §10.4).
    readonly_fields = ("total_budget",)


admin.site.register(SocialPlatformDefinition)
admin.site.register(StreetAdTypeDefinition)
