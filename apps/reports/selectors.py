"""Permission-scoped read queries for dashboards/reports (docs §3, §15.1).
Apply the user's contextual scope (own/team/all) — reports never mutate data."""
from __future__ import annotations

from apps.authorization.services import EffectivePermissionResolver
from apps.leads.constants import ActiveStatus
from apps.leads.models import Lead


def leads_for_user(user, company):
    """Scope leads by the user's effective view permission (docs §4.3 step 6)."""
    base = Lead.objects.filter(company=company).select_related(
        "source", "current_stage", "assigned_salesman", "assigned_team",
        "language", "broker_owner", "campaign",
    )
    if EffectivePermissionResolver.has(user, "leads.lead.view_all"):
        return base
    if EffectivePermissionResolver.has(user, "leads.lead.view_team"):
        team_ids = user.team_memberships.values_list("team_id", flat=True)
        return base.filter(assigned_team_id__in=team_ids)
    return base.filter(assigned_salesman=user)


def active_lead_counts(company):
    return {
        "active": Lead.objects.filter(
            company=company, active_status=ActiveStatus.ACTIVE
        ).count(),
        "inactive": Lead.objects.filter(
            company=company, active_status=ActiveStatus.INACTIVE
        ).count(),
    }
