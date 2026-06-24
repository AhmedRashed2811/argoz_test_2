"""Current-company resolver (docs §2.3). One-company release returns the single
active company; the resolver is the seam a future SaaS app swaps for subdomain/
subscription/user-membership tenant resolution without touching call sites."""
from __future__ import annotations

from django.core.cache import cache

from .models import Company

_CACHE_KEY = "current_company:default"


class CurrentCompanyResolver:
    """All services accept `company` or derive it through this resolver."""

    @staticmethod
    def resolve(request=None) -> Company | None:
        # Future: branch on subdomain / request.user membership / subscription.
        return CurrentCompanyResolver.default_company()

    @staticmethod
    def default_company() -> Company | None:
        company_id = cache.get(_CACHE_KEY)
        if company_id:
            company = Company.objects.filter(id=company_id, is_active=True).first()
            if company:
                return company
        company = Company.objects.filter(is_active=True).order_by("created_at").first()
        if company:
            cache.set(_CACHE_KEY, str(company.id), timeout=300)
        return company

    @staticmethod
    def invalidate() -> None:
        cache.delete(_CACHE_KEY)
