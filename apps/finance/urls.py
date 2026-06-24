"""Finance routes (docs §14)."""
from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("approvals/", views.campaign_approval, name="campaign_approval"),
    path("api/approvals/", views.approval_api_list, name="approval_api_list"),
    path("api/approvals/<uuid:campaign_id>/decide/", views.approval_api_decide,
         name="approval_api_decide"),
    path("approvals/<uuid:campaign_id>/", views.campaign_decide, name="campaign_decide"),
]
