"""Finance routes (docs §14)."""
from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("approvals/", views.campaign_approval, name="campaign_approval"),
    path("approvals/<uuid:campaign_id>/", views.campaign_decide, name="campaign_decide"),
]
