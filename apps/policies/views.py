"""Policy views (docs §7, §14): thin — permission check, delegate to service."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.authorization.decorators import crm_permission_required

from .models import PolicyDefinition
from .services import PolicyManagementService


@login_required
@crm_permission_required("policies.company.manage")
def policy_list(request):
    return render(request, "policies/policy_list.html",
                  PolicyManagementService.get_list_context(company=request.company))


@login_required
@crm_permission_required("policies.company.manage")
def policy_edit(request, policy_id):
    policy = get_object_or_404(PolicyDefinition, id=policy_id, is_active=True)
    context = PolicyManagementService.get_edit_context(
        policy_id=policy_id, company=request.company
    )
    return render(request, "policies/policy_edit.html", context)


@login_required
@crm_permission_required("policies.company.manage")
@require_POST
def policy_api_edit(request, policy_id):
    import json
    policy = get_object_or_404(PolicyDefinition, id=policy_id, is_active=True)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        result = PolicyManagementService.set_value_from_post(
            company=request.company,
            policy=policy,
            post_data=data,
            updated_by=request.user,
            request_meta=request.request_meta,
        )
        return JsonResponse({"ok": True, **result})
    except (ValueError, TypeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
