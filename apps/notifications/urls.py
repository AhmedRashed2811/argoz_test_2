"""Notification routes (docs §14)."""
from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("<uuid:notification_id>/read/", views.mark_read, name="mark_read"),
    path("api/", views.notification_api_list, name="api_list"),
    path("api/<uuid:notification_id>/read/", views.notification_api_mark_read,
         name="api_mark_read"),
    path("api/<uuid:notification_id>/delete/", views.notification_api_delete,
         name="api_delete"),
    path("api/read-all/", views.notification_api_mark_all_read, name="api_mark_all_read"),
    path("sse/", views.notification_sse, name="sse"),
]
