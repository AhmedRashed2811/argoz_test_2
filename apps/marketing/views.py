"""Marketing views (docs §10.3, §14): thin — call CampaignCreationService /
CampaignBudgetService. Views never create child records directly."""
from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.authorization.decorators import crm_permission_required
from apps.core.exceptions import ValidationError

from .forms import CampaignForm, OtherCostForm
from .models import Campaign
from .selectors import campaigns_for_company, campaigns_for_user
from .services import (
    CampaignApprovalService,
    CampaignBudgetService,
    CampaignCreationService,
    CampaignPayloadService,
    CampaignROIService,
)


@login_required
@crm_permission_required("review_marketing_report")
def marketing_report(request):
    """Financial & marketing report (campaign ROI). Thin shell: every figure
    loads via the AJAX endpoint below, which enforces review_marketing_report
    and aggregates through MarketingReportService."""
    return render(request, "marketing/reports.html", {})


@login_required
@crm_permission_required("review_marketing_report")
@require_GET
def marketing_report_api(request):
    """Aggregated campaign budget / lead / KPI figures for the report page.
    Thin: permission check -> service -> JSON. Aggregation lives in the service."""
    from .services.marketing_report_service import MarketingReportService

    return JsonResponse(MarketingReportService.build(request.company))


@login_required
@crm_permission_required("marketing.campaigns.access")
def campaign_list(request):
    restrict_editing = CampaignApprovalService.restrict_editing(request.company)
    approval_required = CampaignApprovalService.approval_required(request.company)
    return render(request, "marketing/campaign_list.html", {
        "restrict_editing": restrict_editing,
        "approval_required": approval_required,
    })


# ── AJAX API for the campaigns page (thin: all work in services, §10.3) ──
@login_required
@crm_permission_required("marketing.campaigns.access")
def campaign_api_list(request):
    campaigns = campaigns_for_user(request.user, request.company).prefetch_related(
        "events__celebrities", "events__giveaways", "events__catering",
        "tv_ads__channels", "tv_ads__slots",
        "street_ads__type_lines__ad_type", "street_ads__type_lines__locations",
        "social_ads__platform_lines__platform", "social_ads__linked_event",
        "exhibitions", "other_costs", "assets",
    )
    return JsonResponse([CampaignPayloadService.serialize(c) for c in campaigns], safe=False)


@login_required
@crm_permission_required("marketing.campaign.create")
@require_POST
def campaign_api_create(request):
    try:
        campaign = CampaignPayloadService.create(
            company=request.company, actor=request.user, payload=json.loads(request.body),
            request_meta=getattr(request, "request_meta", None),
        )
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"id": str(campaign.id)}, status=201)


@login_required
@crm_permission_required("marketing.campaign.update")
@require_POST
def campaign_api_update(request, campaign_id):
    campaign = get_object_or_404(campaigns_for_user(request.user, request.company), id=campaign_id)
    try:
        CampaignPayloadService.update(
            campaign=campaign, actor=request.user, payload=json.loads(request.body),
            request_meta=getattr(request, "request_meta", None),
        )
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"id": str(campaign.id)})


@login_required
@crm_permission_required("marketing.campaign.delete")
@require_POST
def campaign_api_delete(request, campaign_id):
    campaign = get_object_or_404(campaigns_for_user(request.user, request.company), id=campaign_id)
    CampaignPayloadService.delete(
        campaign=campaign, actor=request.user,
        request_meta=getattr(request, "request_meta", None),
    )
    return JsonResponse({"ok": True})


@login_required
@crm_permission_required("marketing.campaign.update")
@require_POST
def event_api_attendance(request, event_id):
    """Set/clear an event's real attendance. Editable regardless of approval
    (no restrict_editing gate) — the event must already exist."""
    from .models import EventRecord
    try:
        CampaignPayloadService.set_event_attendance(
            company=request.company, event_id=event_id,
            actual_attendees=json.loads(request.body).get("actualAttendees"),
            actor=request.user, request_meta=getattr(request, "request_meta", None),
        )
    except EventRecord.DoesNotExist:
        return JsonResponse({"error": "Event not found."}, status=404)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"ok": True})




@login_required
@crm_permission_required("marketing.campaigns.access")
def campaign_detail(request, campaign_id):
    qs = campaigns_for_user(request.user, request.company).prefetch_related(
        "events", "tv_ads", "street_ads", "social_ads", "exhibitions"
    )
    campaign = get_object_or_404(qs, id=campaign_id)
    return render(request, "marketing/campaign_detail.html", {
        "campaign": campaign,
        "roi": CampaignROIService.calculate(campaign=campaign),
        "other_cost_form": OtherCostForm(),
        "approval_required": CampaignApprovalService.approval_required(request.company),
    })


@login_required
@crm_permission_required("marketing.budget.manage")
def campaign_budget(request, campaign_id):
    campaign = get_object_or_404(campaigns_for_user(request.user, request.company), id=campaign_id)
    from apps.marketing.constants import ApprovalStatus

    restrict_editing = CampaignApprovalService.restrict_editing(campaign.company)
    if restrict_editing:
        if campaign.approval_status == ApprovalStatus.APPROVED:
            messages.error(request, "Approved campaigns cannot be edited.")
            return redirect("marketing:campaign_detail", campaign_id=campaign.id)
        elif campaign.approval_status == ApprovalStatus.SEMI_APPROVED:
            rejected = campaign.rejected_budgets or []
            if "other_costs" not in rejected:
                messages.error(request, "Cannot modify approved budgets of a semi-approved campaign.")
                return redirect("marketing:campaign_detail", campaign_id=campaign.id)

    if request.method == "POST":
        form = OtherCostForm(request.POST)
        if form.is_valid():
            total = CampaignBudgetService.add_other_cost(
                campaign=campaign, value=form.cleaned_data["value"],
                reason=form.cleaned_data["reason"], actor=request.user,
            )
        else:
            total = CampaignBudgetService.recalculate(campaign=campaign, actor=request.user)
        messages.success(request, f"Budget recalculated: {total}")
        return redirect("marketing:campaign_detail", campaign_id=campaign.id)
    CampaignBudgetService.recalculate(campaign=campaign, actor=request.user)
    return redirect("marketing:campaign_detail", campaign_id=campaign.id)


@login_required
@crm_permission_required("marketing.campaign.update")
def campaign_update(request, campaign_id):
    campaign = get_object_or_404(campaigns_for_user(request.user, request.company), id=campaign_id)
    from apps.marketing.constants import ApprovalStatus

    restrict_editing = CampaignApprovalService.restrict_editing(campaign.company)
    if restrict_editing:
        if campaign.approval_status == ApprovalStatus.APPROVED:
            messages.error(request, "Approved campaigns cannot be edited.")
            return redirect("marketing:campaign_detail", campaign_id=campaign.id)
        elif campaign.approval_status == ApprovalStatus.SEMI_APPROVED:
            messages.error(request, "Cannot edit a semi-approved campaign through the fallback form.")
            return redirect("marketing:campaign_detail", campaign_id=campaign.id)

    form = CampaignForm(request.POST or None, initial={
        "name": campaign.name, "description": campaign.description,
        "start_date": campaign.start_date, "end_date": campaign.end_date,
        "target_type": campaign.target_type,
    })
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        CampaignCreationService.update_campaign(
            campaign=campaign, actor=request.user,
            request_meta=getattr(request, "request_meta", None),
            name=d["name"], description=d["description"],
            start_date=d["start_date"], end_date=d["end_date"],
            target_type=d["target_type"],
        )
        messages.success(request, "Campaign updated.")
        return redirect("marketing:campaign_detail", campaign_id=campaign.id)
    return render(request, "form.html", {"title": f"Edit: {campaign.name}", "form": form,
                                         "submit_label": "Save"})


@login_required
@crm_permission_required("marketing.campaign.submit_finance")
def campaign_submit_finance(request, campaign_id):
    campaign = get_object_or_404(campaigns_for_user(request.user, request.company), id=campaign_id)
    try:
        CampaignApprovalService.submit_for_finance(
            campaign_id=campaign_id, actor=request.user,
            request_meta=getattr(request, "request_meta", None),
        )
        messages.success(request, "Submitted to finance.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("marketing:campaign_detail", campaign_id=campaign_id)
