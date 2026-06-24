"""Permission-aware navigation (docs §14): top-level menu PageDefinitions the
user may access, by '<module>.<page>.access' code or page-linked permissions."""
from __future__ import annotations

from .models import PageDefinition
from .services import EffectivePermissionResolver


def nav_menu(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"nav_items": []}
    codes = (
        set()
        if not hasattr(user, "is_superuser")
        else EffectivePermissionResolver.get_codes(user)
    )
    items = []
    pages = PageDefinition.objects.filter(
        is_menu_item=True, is_active=True, parent__isnull=True
    ).order_by("module", "menu_order")
    for page in pages:
        access_code = f"{page.module}.{page.code}.access"
        if user.is_superuser or access_code in codes or _page_allowed(page, codes):
            items.append(page)
    return {"nav_items": items}


def _page_allowed(page, codes: set[str]) -> bool:
    return any(p.code in codes for p in page.permissions.all())
