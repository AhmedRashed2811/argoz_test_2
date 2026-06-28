from django.db.models import Count, Q
from django.utils import timezone
from .models import Team, User, Broker


def users_for_company(company):
    return (
        User.objects.filter(profile__company=company)
        .select_related("profile", "profile__default_role")
        .order_by("email")
    )


def user_directory(company):
    """Users + role + teams + active-override count for the directory page."""
    now = timezone.now()
    return (
        User.objects.filter(profile__company=company)
        .select_related("profile", "profile__default_role")
        .prefetch_related("team_memberships__team")
        .annotate(
            overrides_count=Count(
                "permission_overrides",
                filter=Q(permission_overrides__expires_at__isnull=True) | Q(permission_overrides__expires_at__gt=now),
                distinct=True,
            )
        )
        .order_by("first_name", "last_name", "email")
    )


def teams_for_company(company):
    return (
        Team.objects.filter(company=company)
        .select_related("sales_head")
        .prefetch_related("members__user")
        .order_by("order_index", "name")
    )


def _unassigned_or_in_team(company, role_code, team=None):
    """Users with role_code who have no team assignment, plus those already in team."""
    no_team = Q(team_memberships__isnull=True)
    in_this_team = Q(team_memberships__team=team) if team else Q(pk__in=[])
    return (
        User.objects.filter(
            profile__company=company,
            profile__default_role__code=role_code,
            is_active=True,
        )
        .filter(no_team | in_this_team)
        .distinct()
        .select_related("profile")
        .order_by("first_name", "last_name", "email")
    )


def available_heads(company, team=None):
    return _unassigned_or_in_team(company, "SALES_HEAD", team)


def available_members(company, team=None):
    return _unassigned_or_in_team(company, "SALES", team)


def brokers_for_company(company):
    return Broker.objects.filter(company=company).order_by("name")


def broker_detail(company, broker_id):
    return Broker.objects.filter(company=company, id=broker_id).first()


def agencies_for_company(company):
    from .models import Agency

    return Agency.objects.filter(company=company).order_by("name")
