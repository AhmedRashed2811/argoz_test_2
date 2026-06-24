"""Finance views (docs §10.4, §14): thin — delegate to CampaignApprovalService
through the finance façade. Reason rules enforced in form + service."""
from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.authorization.decorators import crm_permission_required
from apps.core.exceptions import ValidationError
from apps.marketing.models import Campaign
from apps.marketing.services import CampaignApprovalService

from .forms import ApprovalForm
from .services import FinanceApprovalService


@login_required
@crm_permission_required("finance.campaign.review")
def campaign_approval(request):
    return render(request, "finance/approval_list.html", {})


# ── AJAX API for the finance approval page (thin: work lives in the service) ──
@login_required
@crm_permission_required("finance.campaign.review")
def approval_api_list(request):
    return JsonResponse(FinanceApprovalService.queue_payload(request.company))


@login_required
@crm_permission_required("finance.campaign.approve")
@require_POST
def approval_api_decide(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, company=request.company)
    data = json.loads(request.body)
    try:
        FinanceApprovalService.decide(
            campaign_id=campaign.id, js_status=data.get("status"),
            actor=request.user, reason=data.get("reason") or "",
            request_meta=getattr(request, "request_meta", None),
        )
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"ok": True})


@login_required
@crm_permission_required("finance.campaign.approve")
def campaign_decide(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, company=request.company)
    form = ApprovalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            CampaignApprovalService.set_status(
                campaign_id=campaign.id, status=form.cleaned_data["status"],
                actor=request.user, reason=form.cleaned_data["reason"],
                request_meta=getattr(request, "request_meta", None),
            )
            messages.success(request, "Approval decision recorded.")
            return redirect("finance:campaign_approval")
        except Exception as exc:
            messages.error(request, str(exc))
    return render(request, "form.html", {
        "title": f"Decision: {campaign.name}", "form": form, "submit_label": "Submit",
    })
