"""Audit log viewer (docs §6, §14): read-only, paginated, filterable. Never
mutates — audit is append-only."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from apps.authorization.decorators import crm_permission_required

from .models import AuditLog


@login_required
@crm_permission_required("audit.view_all")
def audit_list(request):
    qs = AuditLog.objects.filter(company=request.company).select_related("actor")
    action = request.GET.get("action")
    if action:
        qs = qs.filter(action=action)
    entity = request.GET.get("entity_type")
    if entity:
        qs = qs.filter(entity_type=entity)
    page = Paginator(qs.order_by("-created_at"), 50).get_page(request.GET.get("page"))
    return render(request, "audit/audit_list.html", {"page": page})
