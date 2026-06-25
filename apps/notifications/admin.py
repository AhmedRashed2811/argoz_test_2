from django.contrib import admin

from .models import (
    EmailOutbox,
    EmailTemplate,
    Notification,
    NotificationDelivery,
    NotificationType,
)


@admin.register(NotificationType)
class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("company", "recipient", "notification_type", "title", "is_read", "created_at")
    list_filter = ("company", "notification_type", "is_read")
    search_fields = ("title", "body")


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("notification", "channel", "status", "sent_at")
    list_filter = ("channel", "status")


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("company", "code", "subject_template")
    search_fields = ("code", "subject_template")


@admin.register(EmailOutbox)
class EmailOutboxAdmin(admin.ModelAdmin):
    list_display = ("company", "to_email", "subject", "status", "send_after")
    list_filter = ("status",)
    search_fields = ("to_email", "subject")

