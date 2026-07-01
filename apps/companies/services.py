"""Current-company resolver (docs §2.3). One-company release returns the single
active company; the resolver is the seam a future SaaS app swaps for subdomain/
subscription/user-membership tenant resolution without touching call sites."""
from __future__ import annotations

from django.core.cache import cache

from apps.tenants.db import get_current_db

from .models import Company


def _cache_key() -> str:
    # Per-tenant key: the active DB alias scopes the cached company so one
    # tenant's resolution never leaks into another's (DB-per-tenant SaaS).
    return f"current_company:{get_current_db() or 'default'}"


class CurrentCompanyResolver:
    """All services accept `company` or derive it through this resolver."""

    @staticmethod
    def resolve(request=None) -> Company | None:
        # Each tenant DB holds exactly one Company; this returns it.
        return CurrentCompanyResolver.default_company()

    @staticmethod
    def default_company() -> Company | None:
        key = _cache_key()
        company_id = cache.get(key)
        if company_id:
            company = Company.objects.filter(id=company_id, is_active=True).first()
            if company:
                return company
        company = Company.objects.filter(is_active=True).order_by("created_at").first()
        if company:
            cache.set(key, str(company.id), timeout=300)
        return company

    @staticmethod
    def invalidate() -> None:
        cache.delete(_cache_key())
