"""Marketing read queries (docs §15.1, §10.5 lead counts)."""
from django.db.models import Count

from .models import Campaign


def campaigns_for_company(company):
    return (
        Campaign.objects.filter(company=company)
        .select_related("created_by")
        .prefetch_related("selected_types")
        .annotate(lead_count=Count("lead_attributions"))
        .order_by("-created_at")
    )


def campaigns_for_user(user, company):
    from apps.authorization.services import EffectivePermissionResolver

    qs = campaigns_for_company(company)
    if EffectivePermissionResolver.has(user, "marketing.campaign.view_all"):
        return qs
    return qs.filter(created_by=user)

