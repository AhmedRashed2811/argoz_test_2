"""Marketing routes (docs §14)."""
from django.urls import path

from . import views

app_name = "marketing"

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("marketing-report/", views.marketing_report, name="marketing_report"),
    path("api/marketing-report/", views.marketing_report_api, name="api_marketing_report"),
    path("api/campaigns/", views.campaign_api_list, name="campaign_api_list"),
    path("api/campaigns/create/", views.campaign_api_create, name="campaign_api_create"),
    path("api/campaigns/<uuid:campaign_id>/update/", views.campaign_api_update,
         name="campaign_api_update"),
    path("api/campaigns/<uuid:campaign_id>/delete/", views.campaign_api_delete,
         name="campaign_api_delete"),
    path("api/events/<uuid:event_id>/attendance/", views.event_api_attendance,
         name="event_api_attendance"),
    path("<uuid:campaign_id>/", views.campaign_detail, name="campaign_detail"),
    path("<uuid:campaign_id>/edit/", views.campaign_update, name="campaign_update"),
    path("<uuid:campaign_id>/budget/", views.campaign_budget, name="campaign_budget"),
    path("<uuid:campaign_id>/submit/", views.campaign_submit_finance,
         name="campaign_submit_finance"),
]
