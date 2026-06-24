from django.contrib import admin

from .models import EmailTemplate, NotificationType


@admin.register(NotificationType)
class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code",)


admin.site.register(EmailTemplate)
