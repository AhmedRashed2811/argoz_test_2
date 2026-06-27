"""Reusable distribution queries (docs §15.1 selectors). Builds the eligible
candidate pool after the language pre-check + scope mode (§8.4) and computes
candidate load for Round Robin."""
from __future__ import annotations

from django.db.models import Count, Max

from apps.accounts.models import TeamMember
from apps.leads.constants import ActiveStatus, ScopeMode


def eligible_pool(*, company, language=None, scope_mode=ScopeMode.ALL_SALESMEN, team=None):
    """Language-filtered, available TeamMembers per scope mode (docs §8.4)."""
    qs = TeamMember.objects.select_related("team", "user", "user__profile").filter(
        team__company=company, is_available=True, team__is_active=True,
        user__is_active=True, user__profile__availability_status="AVAILABLE"
    )
    if scope_mode in (ScopeMode.TEAM_THEN_SALESMAN, ScopeMode.TEAM_HEAD_DECIDES) and team:
        qs = qs.filter(team=team)
    if language is not None:
        qs = qs.filter(user__languages__language=language).distinct()
    # Stable ordering so the By-Turn pointer maps to a consistent rotation slot
    # across calls (the DB's default order is not guaranteed).
    return list(qs.order_by("user_id"))


MANUAL_DIST_CODE = "leads.distribution.manual_all"


def manual_distributors(company):
    """Users authorized for manual distribution (docs §8.1). Resolved through
    the custom permission layer, not role names (§4.2)."""
    from apps.accounts.models import User
    from apps.authorization.services import EffectivePermissionResolver

    candidates = User.objects.filter(
        is_active=True, profile__company=company
    ).select_related("profile").distinct()
    return [u for u in candidates if EffectivePermissionResolver.has(u, MANUAL_DIST_CODE)]


def candidate_load(user, company):
    """(active lead count, last received lead time) for a salesman (docs §8.3).
    Use batch_candidate_loads() when computing for multiple users at once."""
    from apps.leads.models import Lead, LeadAssignmentHistory

    active_count = Lead.objects.filter(
        company=company, active_status=ActiveStatus.ACTIVE, assigned_salesman=user
    ).count()
    last_received = (
        LeadAssignmentHistory.objects.filter(to_salesman=user, lead__company=company)
        .aggregate(m=Max("assigned_at"))
        .get("m")
    )
    return active_count, last_received


def batch_candidate_loads(users, company) -> dict:
    """Fetch active-lead counts and last-received times for all users in 2 queries.
    Returns {user_id: (active_count, last_received_at)} — eliminates N+1 in Round Robin."""
    from apps.leads.models import Lead, LeadAssignmentHistory

    user_ids = [u.pk for u in users]
    if not user_ids:
        return {}

    active_counts = dict(
        Lead.objects.filter(
            company=company,
            active_status=ActiveStatus.ACTIVE,
            assigned_salesman__in=user_ids,
        )
        .values("assigned_salesman")
        .annotate(c=Count("id"))
        .values_list("assigned_salesman", "c")
    )
    last_received = dict(
        LeadAssignmentHistory.objects.filter(
            to_salesman__in=user_ids, lead__company=company
        )
        .values("to_salesman")
        .annotate(m=Max("assigned_at"))
        .values_list("to_salesman", "m")
    )
    return {
        uid: (active_counts.get(uid, 0), last_received.get(uid))
        for uid in user_ids
    }
