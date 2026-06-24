from django.contrib import admin

from .models import Branch, Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "subscription_status", "plan_code")


admin.site.register(Branch)
