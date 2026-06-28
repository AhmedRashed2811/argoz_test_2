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
    ).order_by("menu_order", "name")
    for page in pages:
        if page.module == "notifications":
            continue
        access_code = f"{page.code}.access"
        if user.is_superuser or access_code in codes or _page_allowed(page, codes):
            # Resolve allowed children
            allowed_children = []
            for child in page.children.filter(is_menu_item=True, is_active=True).order_by("menu_order", "name"):
                child_access = f"{child.code}.access"
                if user.is_superuser or child_access in codes or _page_allowed(child, codes):
                    allowed_children.append(child)
            page.allowed_children = allowed_children
            items.append(page)

    # Brokers get a dedicated read-only "Leads" link to the All-Leads page,
    # self-scoped by view_own (the page/api filter to their own leads).
    show_broker_leads = (
        "leads.lead.view_own" in codes
        and hasattr(user, "broker_profile")
        and user.broker_profile.exists()
    )
    return {"nav_items": items, "show_broker_leads": show_broker_leads}


def _page_allowed(page, codes: set[str]) -> bool:
    access_perms = [p for p in page.permissions.all() if p.code.endswith(".access")]
    if access_perms:
        return any(p.code in codes for p in access_perms)
    return any(p.code in codes for p in page.permissions.all())
