"""Lead routes (docs §14). Namespaced; templates use {% url 'leads:...' %}."""
from django.urls import path

from . import api, views

app_name = "leads"

urlpatterns = [
    path("", views.lead_list, name="list"),
    path("create/", views.lead_create, name="create"),
    path("walkin/", views.walkin_create, name="walkin_create"),
    # --- AJAX/JSON endpoints for the dynamic create page ---
    path("api/create/", api.api_create, name="api_create"),
    path("api/sources/", api.api_sources, name="api_sources"),
    path("api/languages/", api.api_languages, name="api_languages"),
    path("api/duplicate-check/", api.api_duplicate_check, name="api_duplicate_check"),
    path("api/existing-client/", api.api_existing_client, name="api_existing_client"),
    path("api/campaigns/", api.api_campaigns, name="api_campaigns"),
    path("api/campaign-channels/", api.api_campaign_channels, name="api_campaign_channels"),
    path("api/campaign-children/", api.api_campaign_children, name="api_campaign_children"),
    path("api/records/", api.api_records, name="api_records"),
    path("api/walkin-state/", api.api_walkin_state, name="api_walkin_state"),
    path("api/walkin-advance/", api.api_walkin_advance, name="api_walkin_advance"),
    path("api/brokers/", api.api_brokers, name="api_brokers"),
    path("api/salesmen/", api.api_salesmen, name="api_salesmen"),
    path("api/team-members/", api.api_team_members, name="api_team_members"),
    path("api/teams/", api.api_teams, name="api_teams"),
    path("api/cc-agents/", api.api_cc_agents, name="api_cc_agents"),
    path("api/walkin-rotation/", api.api_walkin_rotation, name="api_walkin_rotation"),
    path("<uuid:lead_id>/", views.lead_detail, name="detail"),
    path("<uuid:lead_id>/assign/", views.lead_assign, name="assign"),
    path("<uuid:lead_id>/followup/", views.followup_create, name="followup_create"),
    path("<uuid:lead_id>/meeting/", views.meeting_create, name="meeting_create"),
    path("<uuid:lead_id>/stage/", views.stage_change, name="stage_change"),
]
