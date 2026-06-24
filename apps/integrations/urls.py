"""Integration webhook routes (docs §13.2 tenant-specific URL)."""
from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("webhooks/", views.webhook_list, name="webhook_list"),
    path("webhooks/create/", views.webhook_create, name="webhook_create"),
    path("webhooks/<uuid:endpoint_uuid>/", views.receive_webhook, name="receive_webhook"),
]
