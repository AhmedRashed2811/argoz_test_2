"""Lead routes (docs §14). Namespaced; templates use {% url 'leads:...' %}."""
from django.urls import path

from . import api, views

app_name = "leads"

urlpatterns = [
    path("", views.lead_list, name="list"),
    path("all/", views.all_leads, name="all_list"),
    path("manual-distribution/", views.manual_distribution, name="manual_distribution"),
    path("create/", views.lead_create, name="create"),
    path("walkin/", views.walkin_create, name="walkin_create"),
    path("sales-performance/", views.sales_performance, name="sales_performance"),
    path("api/sales-performance/", api.api_sales_performance, name="api_sales_performance"),
    path("leads-analysis/", views.leads_analysis, name="leads_analysis"),
    path("api/leads-analysis/", api.api_leads_analysis, name="api_leads_analysis"),
    # --- AJAX/JSON endpoints for the dynamic management page ---
    path("api/leads/", api.api_leads, name="api_leads"),
    path("api/lead-history/", api.api_lead_history, name="api_lead_history"),
    path("api/stage-update/", api.api_stage_update, name="api_stage_update"),
    # --- AJAX/JSON endpoints for the All-Leads admin database page ---
    path("api/all-leads/", api.api_all_leads, name="api_all_leads"),
    path("api/all-lead-history/", api.api_all_lead_history, name="api_all_lead_history"),
    path("api/lead-set-active/", api.api_lead_set_active, name="api_lead_set_active"),
    path("api/lead-edit/", api.api_lead_edit, name="api_lead_edit"),
    # --- AJAX/JSON endpoints for the manual distribution board ---
    path("api/manual-dist/leads/", api.api_manual_dist_leads, name="api_manual_dist_leads"),
    path("api/manual-dist/salesmen/", api.api_manual_dist_salesmen, name="api_manual_dist_salesmen"),
    path("api/manual-dist/history/", api.api_manual_dist_history, name="api_manual_dist_history"),
    path("api/manual-dist/assign/", api.api_manual_dist_assign, name="api_manual_dist_assign"),
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
