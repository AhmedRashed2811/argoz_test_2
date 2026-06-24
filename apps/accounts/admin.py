from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Broker, Language, Team, TeamMember, User, UserLanguage, UserProfile


@admin.register(User)
class CRMUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "phone")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser",
                                    "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "username", "password1", "password2")}),
    )


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "sales_head", "order_index", "is_active")
    inlines = [TeamMemberInline]


admin.site.register(UserProfile)
admin.site.register(Language)
admin.site.register(UserLanguage)
admin.site.register(Broker)
