"""Marketing views (docs §10.3, §14): thin — call CampaignCreationService /
CampaignBudgetService. Views never create child records directly."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.authorization.decorators import crm_permission_required

from .forms import CampaignForm, OtherCostForm
from .models import Campaign, OtherCost
from .selectors import campaigns_for_company
from .services import (
    CampaignApprovalService,
    CampaignBudgetService,
    CampaignCreationService,
    CampaignROIService,
)


@login_required
@crm_permission_required("marketing.campaigns.access")
def campaign_list(request):
    return render(request, "marketing/campaign_list.html", {
        "campaigns": campaigns_for_company(request.company),
    })


@login_required
@crm_permission_required("marketing.campaign.create")
def campaign_create(request):
    form = CampaignForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        campaign = CampaignCreationService.create_campaign(
            company=request.company, actor=request.user, name=d["name"],
            description=d["description"], start_date=d["start_date"],
            end_date=d["end_date"], target_type=d["target_type"],
            selected_types=d["selected_types"],
            request_meta=getattr(request, "request_meta", None),
        )
        messages.success(request, "Campaign created.")
        return redirect("marketing:campaign_detail", campaign_id=campaign.id)
    return render(request, "form.html", {"title": "New campaign", "form": form,
                                         "submit_label": "Create"})


@login_required
@crm_permission_required("marketing.campaigns.access")
def campaign_detail(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, company=request.company)
    return render(request, "marketing/campaign_detail.html", {
        "campaign": campaign,
        "roi": CampaignROIService.calculate(campaign=campaign),
        "other_cost_form": OtherCostForm(),
    })


@login_required
@crm_permission_required("marketing.budget.manage")
def campaign_budget(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, company=request.company)
    if request.method == "POST":
        form = OtherCostForm(request.POST)
        if form.is_valid():
            OtherCost.objects.create(
                campaign=campaign, value=form.cleaned_data["value"],
                reason=form.cleaned_data["reason"], created_by=request.user,
            )
        total = CampaignBudgetService.recalculate(campaign=campaign, actor=request.user)
        messages.success(request, f"Budget recalculated: {total}")
        return redirect("marketing:campaign_detail", campaign_id=campaign.id)
    CampaignBudgetService.recalculate(campaign=campaign, actor=request.user)
    return redirect("marketing:campaign_detail", campaign_id=campaign.id)


@login_required
@crm_permission_required("marketing.campaign.create")
def campaign_update(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, company=request.company)
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
    try:
        CampaignApprovalService.submit_for_finance(
            campaign_id=campaign_id, actor=request.user,
            request_meta=getattr(request, "request_meta", None),
        )
        messages.success(request, "Submitted to finance.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("marketing:campaign_detail", campaign_id=campaign_id)
