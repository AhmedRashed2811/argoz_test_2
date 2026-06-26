"""Lead views (docs §4.5, §14): thin — permission check, form, service call,
redirect/render. No business logic; all writes go through services."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.authorization.decorators import crm_permission_required
from apps.reports.selectors import leads_for_user

from .forms import (
    FollowUpForm,
    ManualAssignmentForm,
    MeetingForm,
    StageChangeForm,
    WalkInForm,
)
from .models import Lead
from .services import (
    FollowUpService,
    LeadStageService,
    MeetingService,
    WalkInService,
)


@login_required
@crm_permission_required("leads.dashboard.access")
def lead_list(request):
    # Scope is applied by the selector via the effective permission set (§4.3).
    return render(request, "leads/lead_list.html", {
        "leads": leads_for_user(request.user, request.company)[:200],
    })


@login_required
def lead_detail(request, lead_id):
    lead = get_object_or_404(
        Lead.objects.select_related(
            "source", "current_stage", "assigned_salesman", "assigned_team",
            "language", "broker_owner", "campaign", "created_by", "company",
        ).prefetch_related(
            "followups", "meetings", "lead_notes", "activities",
            "stage_history__from_stage", "stage_history__to_stage",
            "assignment_history__to_salesman", "assignment_history__from_salesman",
            "broker_ownership_history",
        ),
        id=lead_id,
        company=request.company,
    )
    return render(request, "leads/lead_detail.html", {
        "lead": lead,
        "assign_form": ManualAssignmentForm(company=request.company),
        "followup_form": FollowUpForm(),
        "meeting_form": MeetingForm(),
        "stage_form": StageChangeForm(),
    })


@login_required
@crm_permission_required("leads.dashboard.access")
def lead_create(request):
    """Dynamic lead-creation page (leads spec §4). The page itself is thin: it
    renders the shell; all data and submission go through the AJAX endpoints in
    api.py, which enforce per-source permissions and route to services."""
    return render(request, "leads/lead_create.html", {})


@login_required
@crm_permission_required("leads.distribution.manual_all")
def lead_assign(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id, company=request.company)
    form = ManualAssignmentForm(request.POST or None, company=request.company)
    if request.method == "POST" and form.is_valid():
        from apps.distribution.services import ManualAssignmentService

        d = form.cleaned_data
        meta = getattr(request, "request_meta", None)
        if d["salesman"]:
            ManualAssignmentService.assign_to_salesman(
                lead_id=lead.id, salesman=d["salesman"], team=d["team"],
                actor=request.user, reason=d["reason"], request_meta=meta,
            )
        else:
            ManualAssignmentService.assign_to_team(
                lead_id=lead.id, team=d["team"], actor=request.user,
                reason=d["reason"], request_meta=meta,
            )
        messages.success(request, "Lead assigned.")
        return redirect("leads:detail", lead_id=lead.id)
    return render(request, "form.html", {"title": "Assign lead", "form": form})


@login_required
@crm_permission_required("leads.followup.create_own")
def followup_create(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id, company=request.company)
    form = FollowUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        FollowUpService.schedule(
            lead_id=lead.id, scheduled_at=form.cleaned_data["scheduled_at"],
            actor=request.user, notes=form.cleaned_data["notes"],
            request_meta=getattr(request, "request_meta", None),
        )
        messages.success(request, "Follow-up scheduled.")
        return redirect("leads:detail", lead_id=lead.id)
    return render(request, "form.html", {"title": "Schedule follow-up", "form": form})


@login_required
@crm_permission_required("leads.meeting.create_own")
def meeting_create(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id, company=request.company)
    form = MeetingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        MeetingService.schedule(
            lead_id=lead.id, scheduled_start=d["scheduled_start"],
            scheduled_end=d["scheduled_end"], location=d["location"],
            actor=request.user, request_meta=getattr(request, "request_meta", None),
        )
        messages.success(request, "Meeting scheduled.")
        return redirect("leads:detail", lead_id=lead.id)
    return render(request, "form.html", {"title": "Schedule meeting", "form": form})


@login_required
@crm_permission_required("leads.lead.create_any_source")
def walkin_create(request):
    """Walk-in lead intake (leads spec §4.2d). Calls WalkInService which
    applies the company-configured reception policy."""
    form = WalkInForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            lead = WalkInService.register(
                company=request.company, name=d["name"], phone=d["phone"],
                how_did_you_know=d["how_did_you_know"],
                receptionist=request.user, actor=request.user,
                request_meta=getattr(request, "request_meta", None),
            )
            messages.success(request, "Walk-in lead registered.")
            return redirect("leads:detail", lead_id=lead.id)
        except Exception as exc:
            messages.error(request, str(exc))
    return render(request, "form.html", {"title": "Walk-in Lead", "form": form,
                                         "submit_label": "Register"})


@login_required
@crm_permission_required("leads.stage.change_own")
def stage_change(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id, company=request.company)
    form = StageChangeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        LeadStageService.change_stage(
            lead_id=lead.id, to_stage_code=form.cleaned_data["to_stage_code"],
            actor=request.user, reason=form.cleaned_data["reason"],
            request_meta=getattr(request, "request_meta", None),
        )
        messages.success(request, "Stage updated.")
        return redirect("leads:detail", lead_id=lead.id)
    return render(request, "form.html", {"title": "Change stage", "form": form})
