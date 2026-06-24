"""Notification routes (docs §14)."""
from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("<uuid:notification_id>/read/", views.mark_read, name="mark_read"),
]
