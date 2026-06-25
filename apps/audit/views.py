"""Audit log viewer (docs §6, §14): read-only, paginated, filterable. Never
mutates — audit is append-only."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from apps.authorization.decorators import crm_permission_required

from .models import AuditLog


from django.http import JsonResponse


@login_required
@crm_permission_required("audit.view_all")
def audit_list(request):
    """Renders layout shell for dynamically loaded audit trail page."""
    return render(request, "audit/audit_list.html")


@login_required
@crm_permission_required("audit.view_all")
def audit_api_list(request):
    """Serve JSON list of system audit trail logs with filtering & KPIs."""
    from .services import AuditService
    filters = {
        "action": request.GET.get("action"),
        "entity_type": request.GET.get("entity_type"),
        "limit": request.GET.get("limit", 100),
        "page": request.GET.get("page", 1),
    }
    payload = AuditService.get_audit_logs_payload(
        company=request.company,
        filters=filters,
        is_permission_audit=False
    )
    return JsonResponse(payload)


