"""Marketing routes (docs §14)."""
from django.urls import path

from . import views

app_name = "marketing"

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("create/", views.campaign_create, name="campaign_create"),
    path("<uuid:campaign_id>/", views.campaign_detail, name="campaign_detail"),
    path("<uuid:campaign_id>/edit/", views.campaign_update, name="campaign_update"),
    path("<uuid:campaign_id>/budget/", views.campaign_budget, name="campaign_budget"),
    path("<uuid:campaign_id>/submit/", views.campaign_submit_finance,
         name="campaign_submit_finance"),
]
