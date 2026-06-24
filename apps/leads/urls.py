"""Lead routes (docs §14). Namespaced; templates use {% url 'leads:...' %}."""
from django.urls import path

from . import views

app_name = "leads"

urlpatterns = [
    path("", views.lead_list, name="list"),
    path("create/", views.lead_create, name="create"),
    path("walkin/", views.walkin_create, name="walkin_create"),
    path("<uuid:lead_id>/", views.lead_detail, name="detail"),
    path("<uuid:lead_id>/assign/", views.lead_assign, name="assign"),
    path("<uuid:lead_id>/followup/", views.followup_create, name="followup_create"),
    path("<uuid:lead_id>/meeting/", views.meeting_create, name="meeting_create"),
    path("<uuid:lead_id>/stage/", views.stage_change, name="stage_change"),
]
