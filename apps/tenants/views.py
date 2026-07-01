"""SaaS control-plane panel (thin views: gate -> parse -> service -> JSON).
All mutations are AJAX; the list page is the only rendered template."""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .decorators import superadmin_required
from .models import Tenant
from .services import TenantError, TenantProvisioningService, TenantService


def _row(t: Tenant) -> dict:
    from apps.accounts.models import User
    from .db import ensure_connection, set_current_db, clear_current_db

    alias = ensure_connection(t)
    set_current_db(alias)
    try:
        admin_user = User.objects.filter(is_superuser=True).first()
        admin_email = admin_user.email if admin_user else "—"
    except Exception:
        admin_email = "—"
    finally:
        clear_current_db()

    return {
        "id": t.id,
        "name": t.name,
        "slug": t.slug,
        "db_name": t.db_name,
        "is_active": t.is_active,
        "paid_until": t.paid_until.isoformat() if t.paid_until else "",
        "notes": t.notes,
        "url": f"/t/{t.slug}/",
        "created_at": t.created_at.strftime("%Y-%m-%d"),
        "admin_email": admin_email,
    }


@ensure_csrf_cookie
@superadmin_required
def tenant_list(request):
    return render(request, "tenants/admin_list.html")


@superadmin_required
def tenant_api_list(request):
    return JsonResponse({"tenants": [_row(t) for t in Tenant.objects.all()]})


@superadmin_required
@require_POST
def tenant_api_create(request):
    data = json.loads(request.body or "{}")
    try:
        tenant = TenantProvisioningService.provision(
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            admin_email=data.get("admin_email", ""),
            admin_password=data.get("admin_password", ""),
            paid_until=data.get("paid_until") or None,
            notes=data.get("notes", ""),
        )
    except TenantError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "tenant": _row(tenant)})


@superadmin_required
@require_POST
def tenant_api_toggle(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    data = json.loads(request.body or "{}")
    TenantService.set_active(tenant, active=bool(data.get("active")))
    return JsonResponse({"ok": True, "tenant": _row(tenant)})


@superadmin_required
@require_POST
def tenant_api_update(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    data = json.loads(request.body or "{}")
    TenantService.update_subscription(
        tenant, paid_until=data.get("paid_until"), notes=data.get("notes"),
    )
    return JsonResponse({"ok": True, "tenant": _row(tenant)})
