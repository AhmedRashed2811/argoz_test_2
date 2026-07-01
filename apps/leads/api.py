"""AJAX/JSON endpoints for the dynamic lead-creation page (leads spec §4).
Thin: permission check -> selector/service -> JSON. No business logic here;
creation routes through SourceRouterService."""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from datetime import datetime

from django.utils import timezone

from apps.accounts.models import Language, Team
from apps.authorization.decorators import crm_permission_required
from apps.authorization.services import EffectivePermissionResolver
from apps.core.exceptions import PermissionDenied, ValidationError
from apps.distribution.selectors import eligible_pool

from .constants import SourceCode, StageCode
from .services import (
    BulkLeadImportService,
    DuplicateService,
    FollowUpService,
    LeadApiService,
    LeadSerializationService,
    LeadStageService,
    ManualDistributionService,
    MeetingService,
    SourceRouterService,
)

# Sources exposed in the UI, with a stable label + the default per role order.
_SOURCE_LABELS = {
    SourceCode.SELF_GENERATED: "Self-Generated",
    SourceCode.CAMPAIGN: "Campaign",
    SourceCode.BROKER: "Broker",
    SourceCode.WALK_IN: "Walk-in",
    SourceCode.CALL_CENTER: "Call Center",
    SourceCode.EXHIBITION: "Exhibition",
    SourceCode.REFERRAL: "Referral",
    SourceCode.EXISTING_CLIENT: "Existing Client",
}


def _err(message, status=400):
    return JsonResponse({"ok": False, "error": str(message)}, status=status)


@login_required
@require_GET
def api_sources(request):
    """Sources the logged-in user may create from (§4.2b drives the UI buttons)."""
    allowed = [
        {"code": code.lower(), "label": label}
        for code, label in _SOURCE_LABELS.items()
        if EffectivePermissionResolver.has(
            request.user, f"leads.lead.create_from_{code.lower()}"
        )
    ]
    own_broker = (
        request.user.broker_profile.filter(company=request.company).first()
        if hasattr(request.user, "broker_profile") else None
    )
    is_broker = own_broker is not None
    is_head = Team.objects.filter(
        company=request.company, sales_head=request.user
    ).exists()
    is_salesman = request.user.team_memberships.filter(
        team__company=request.company
    ).exists() and not is_head
    can_manual = any(
        EffectivePermissionResolver.has(request.user, c)
        for c in ("leads.distribution.manual_all", "leads.distribution.team_manual")
    )
    from apps.policies.constants import PolicyCode
    from apps.policies.services import PolicyResolver
    head_assignment = PolicyResolver.option_code(
        request.company, PolicyCode.SELF_GENERATED_HEAD_ASSIGNMENT,
        default="SELF_OR_MANUAL_TEAM")
    broker_also_assign_salesman = bool(PolicyResolver.value(
        request.company, PolicyCode.BROKER_ALSO_ASSIGN_SALESMAN, default=False
    ))
    return JsonResponse({
        "sources": allowed, "is_broker": is_broker,
        "broker_name": own_broker.name if own_broker else "",
        "is_head": is_head,
        "is_salesman": is_salesman, "can_manual": can_manual,
        "head_assignment": head_assignment,
        "broker_also_assign_salesman": broker_also_assign_salesman,
    })


@login_required
@crm_permission_required("leads.calendar.access")
@require_GET
def api_calendar(request):
    """Scoped calendar events for the visible month grid (padded one week each
    side so leading/trailing days render correctly). Read-only selector call."""
    from datetime import timedelta

    from .selectors import calendar_events

    now = timezone.localtime()
    try:
        year = int(request.GET.get("year", now.year))
        month = int(request.GET.get("month", now.month))
        first = datetime(year, month, 1)
    except (TypeError, ValueError):
        return _err("Invalid year/month")
    nxt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    start = timezone.make_aware(first) - timedelta(days=7)
    end = timezone.make_aware(nxt) + timedelta(days=7)
    return JsonResponse({
        "ok": True,
        "events": calendar_events(request.user, request.company, start, end),
    })


@login_required
@require_GET
def api_languages(request):
    return JsonResponse({"languages": [
        {"id": str(l.id), "name": l.name, "code": l.code}
        for l in Language.objects.filter(is_active=True).order_by("name")
    ]})


@login_required
@require_GET
def api_duplicate_check(request):
    phone = (request.GET.get("phone") or "").strip()
    if not phone:
        return JsonResponse({"is_duplicate": False})
    dup = DuplicateService.check(company=request.company, phone=phone)
    payload = {"is_duplicate": dup.is_duplicate, "requires_manual": dup.requires_manual}
    if dup.existing is not None:
        e = dup.existing
        payload["existing"] = {
            "id": str(e.id), "name": e.name, "phone": e.phone,
            "source": e.source.name if e.source_id else "",
            "stage": e.current_stage.name if e.current_stage_id else "",
            "salesman": e.assigned_salesman.get_full_name()
            if e.assigned_salesman_id else "",
        }
    return JsonResponse(payload)


@login_required
@require_GET
def api_existing_client(request):
    from .selectors import existing_client

    client = existing_client(request.company, request.GET.get("phone"))
    if client is None:
        return JsonResponse({"found": False})
    sm = client.original_salesman
    return JsonResponse({"found": True, "client": {
        "id": str(client.id), "name": client.name, "phone": client.phone,
        "original_salesman": sm.get_full_name() if sm else "",
        "original_salesman_active": bool(sm and sm.is_active),
        "status": client.status,
    }})


@login_required
@require_GET
def api_campaigns(request):
    from apps.marketing.selectors import active_campaigns

    return JsonResponse({"campaigns": [
        {"id": str(c.id), "name": c.name}
        for c in active_campaigns(request.company)
    ]})


@login_required
@require_GET
def api_campaign_channels(request):
    """The channels a chosen campaign actually has (events-only campaign won't
    offer Social Media, etc.)."""
    from apps.marketing.selectors import campaign_available_channels, campaign_for_company

    campaign = campaign_for_company(request.company, request.GET.get("campaign"))
    if campaign is None:
        return _err("Unknown campaign.")
    return JsonResponse({"channels": campaign_available_channels(campaign)})


@login_required
@require_GET
def api_campaign_children(request):
    from apps.marketing.selectors import campaign_for_company, channel_records

    campaign = campaign_for_company(request.company, request.GET.get("campaign"))
    if campaign is None:
        return _err("Unknown campaign.")
    return JsonResponse({"items": channel_records(
        company=request.company, fe_channel=request.GET.get("channel", ""),
        campaign=campaign, platform_id=request.GET.get("platform") or None)})


@login_required
@require_GET
def api_records(request):
    """Company-wide marketing records for a channel — used by Walk-in / Call
    Center / Exhibition capture (not scoped to one campaign)."""
    from apps.marketing.selectors import channel_records

    return JsonResponse({"items": channel_records(
        company=request.company, fe_channel=request.GET.get("type", ""),
        campaign=None, platform_id=request.GET.get("platform") or None)})


@login_required
@require_GET
def api_walkin_state(request):
    """Walk-in reception policy + live rotation cursor (whose turn it is)."""
    from apps.policies.constants import PolicyCode
    from apps.policies.services import PolicyResolver
    from apps.leads.services.walkin_service import WalkInService

    policy = PolicyResolver.option_code(
        request.company, PolicyCode.WALKIN_RECEPTION_POLICY, default="OPEN_FLOOR")
    return JsonResponse(WalkInService.rotation_state(request.company, policy))


@login_required
@require_POST
def api_walkin_advance(request):
    """Advance a rotation cursor: full-rotation 'skip' or team-turn 'pass to next
    team'. Persists the pointer move server-side (leads spec §4.2d)."""
    from apps.policies.constants import PolicyCode
    from apps.policies.services import PolicyResolver
    from apps.leads.services.walkin_service import WalkInService

    policy = PolicyResolver.option_code(
        request.company, PolicyCode.WALKIN_RECEPTION_POLICY, default="OPEN_FLOOR")
    WalkInService.advance_for_policy(request.company, policy)
    return JsonResponse(WalkInService.rotation_state(request.company, policy))


@login_required
@require_GET
def api_brokers(request):
    from .selectors import active_brokers

    return JsonResponse({"brokers": [
        {"id": str(b.id), "name": b.name}
        for b in active_brokers(request.company)
    ]})


def _people(members):
    seen, out = set(), []
    for m in members:
        u = m.user
        if u.id in seen:
            continue
        seen.add(u.id)
        out.append({"id": str(u.id), "name": u.get_full_name() or u.email,
                    "team": m.team.name, "team_id": str(m.team_id)})
    return out


@login_required
@require_GET
def api_salesmen(request):
    """Available salesmen, language-filtered when a language is given (§8.4 req 7a)."""
    language = Language.objects.filter(
        code=(request.GET.get("language") or "").strip()
    ).first()
    pool = eligible_pool(company=request.company, language=language)
    return JsonResponse({"salesmen": _people(pool)})


@login_required
@require_GET
def api_team_members(request):
    """Members of the logged-in head's own team(s) (self-generated → member)."""
    from .selectors import head_team_members

    return JsonResponse({"members": _people(
        head_team_members(request.user, request.company))})


@login_required
@require_GET
def api_teams(request):
    from .selectors import active_teams

    return JsonResponse({"teams": [
        {"id": str(t.id), "name": t.name}
        for t in active_teams(request.company)
    ]})


@login_required
@require_GET
def api_cc_agents(request):
    """Actual Call Center agents (§4.2g) — users in the CALL_CENTER role, not
    everyone who happens to hold the call-center create permission."""
    from .selectors import call_center_agents

    return JsonResponse({"agents": [
        {"id": str(u.id), "name": u.get_full_name() or u.email}
        for u in call_center_agents(request.company)
    ]})


@login_required
@require_GET
def api_walkin_rotation(request):
    """Current walk-in policy + rotation order so the receptionist sees whose
    turn it is (§4.2d). Order is the live company-wide By-Turn order."""
    from apps.policies.constants import PolicyCode
    from apps.policies.services import PolicyResolver

    policy = PolicyResolver.option_code(
        request.company, PolicyCode.WALKIN_RECEPTION_POLICY, default="OPEN_FLOOR"
    )
    from .selectors import active_teams

    pool = eligible_pool(company=request.company)
    return JsonResponse({
        "policy": policy,
        "rotation_order": _people(pool),
        "teams": [{"id": str(t.id), "name": t.name}
                  for t in active_teams(request.company)],
    })


@login_required
@require_POST
def api_create(request):
    """Create a lead from any source the user is permitted to use (§4.2)."""
    try:
        data = json.loads(request.body.decode() or "{}")
    except ValueError:
        return _err("Malformed request.")
    source_code = data.get("source_code", "").upper()
    # Resolve the language code (static UI list) to a Language row if one exists.
    code = (data.get("language_code") or "").strip()
    data["language"] = (
        Language.objects.filter(code=code, is_active=True).first() if code else None
    )
    try:
        lead = SourceRouterService.create_lead(
            company=request.company, actor=request.user, source_code=source_code,
            data=data, request_meta=getattr(request, "request_meta", None),
        )
    except PermissionDenied as exc:
        return _err(exc, status=403)
    except ValidationError as exc:
        return _err(exc, status=400)
    from django.urls import reverse

    resp = {
        "ok": True, "lead_id": str(lead.id),
        "redirect": reverse("leads:detail", args=[lead.id]),
    }
    action = getattr(lead, "_duplicate_action", None)
    if action:
        resp["duplicate"] = True
        resp["duplicate_action"] = action
    return JsonResponse(resp)


@login_required
@crm_permission_required("leads.lead.bulk_create")
@require_POST
def api_bulk_import(request):
    """Import leads from an uploaded CSV. Validation, dedup and creation live in
    BulkLeadImportService; this view only checks the file and returns the summary."""
    upload = request.FILES.get("file")
    if upload is None:
        return _err("Attach a CSV file.")
    result = BulkLeadImportService.import_csv(
        company=request.company, actor=request.user,
        file_bytes=upload.read(),
        request_meta=getattr(request, "request_meta", None),
    )
    if "error" in result:
        return _err(result["error"])
    return JsonResponse({"ok": True, **result})


@login_required
@crm_permission_required("leads.lead.bulk_create")
@require_POST
def api_bulk_reactivate(request):
    """Reactivate the existing leads for the given phones (manual distribution,
    no SLA, no notification) after the importer confirms in the modal."""
    try:
        phones = json.loads(request.body.decode() or "{}").get("phones", [])
    except ValueError:
        return _err("Malformed request.")
    count = BulkLeadImportService.reactivate(
        company=request.company, actor=request.user, phones=phones,
        request_meta=getattr(request, "request_meta", None),
    )
    return JsonResponse({"ok": True, "reactivated": count})


@login_required
@crm_permission_required("leads.lead.bulk_create")
@require_POST
def api_rejected_export(request):
    """Return the rejected import rows as an .xlsx with the value cells filled
    light red (task 9). The rows come back from the import summary, so no
    re-validation happens here — this is a pure formatting/export endpoint."""
    from django.http import HttpResponse

    try:
        data = json.loads(request.body.decode() or "{}")
    except ValueError:
        return _err("Malformed request.")
    rows = data.get("rows") or []
    columns = data.get("columns") or []
    if not rows:
        return _err("Nothing to export.")
    content = BulkLeadImportService.build_rejected_xlsx(rows=rows, columns=columns)
    resp = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = 'attachment; filename="rejected_leads.xlsx"'
    return resp


# ── Leads analysis report page (leads_analysis.html) ──────────────────────────

@login_required
@crm_permission_required("review_leads_analysis")
@require_GET
def api_leads_analysis(request):
    """Company-wide pipeline analytics for the leads-analysis page. Thin:
    permission check -> service -> JSON. Aggregation lives in the service."""
    from .services.leads_analysis_service import LeadsAnalysisService

    return JsonResponse(LeadsAnalysisService.build(request.company))


# ── Sales performance report page (sales_performance.html) ────────────────────

@login_required
@crm_permission_required("review_sales_performance_report")
@require_GET
def api_sales_performance(request):
    """Per-salesperson / per-team performance + funnel figures. Thin: permission
    check -> service -> JSON. Scoping and aggregation live in the service."""
    from .services.sales_performance_service import SalesPerformanceService

    return JsonResponse(SalesPerformanceService.build(request.user, request.company))


# ── Sales-leads management page (lead_list.html) ──────────────────────────────

def _combine(date_str, time_str, *, default_time="09:00"):
    """Combine 'YYYY-MM-DD' + 'HH:MM' into an aware datetime."""
    if not date_str:
        raise ValidationError("A date is required.")
    dt = datetime.strptime(f"{date_str} {time_str or default_time}", "%Y-%m-%d %H:%M")
    return timezone.make_aware(dt, timezone.get_current_timezone())


@login_required
@crm_permission_required("leads.dashboard.access")
@require_GET
def api_leads(request):
    """Leads the user may see (scoped by view permission), shaped for the table."""
    from apps.reports.selectors import leads_for_user
    from apps.policies.constants import PolicyCode
    from apps.policies.services import PolicyResolver
    from .constants import ActiveStatus

    qs = leads_for_user(request.user, request.company)
    # Task 1b: when the company turns off "salesman sees inactive leads" (On by
    # default), the sales management page shows only the salesman's active leads.
    if not PolicyResolver.value(request.company, PolicyCode.SALES_VIEW_INACTIVE, default=True):
        qs = qs.filter(active_status=ActiveStatus.ACTIVE)
    return JsonResponse({"leads": LeadSerializationService.rows(list(qs))})


@login_required
@crm_permission_required("leads.dashboard.access")
@require_GET
def api_lead_history(request):
    """Timeline for one lead (sales management page)."""
    from .selectors import lead_detail_qs

    lead = lead_detail_qs().filter(
        id=request.GET.get("lead_id"), company=request.company
    ).first()
    if lead is None:
        return _err("Lead not found.", status=404)
    return JsonResponse({"history": LeadSerializationService.history(lead)})


@login_required
@crm_permission_required("leads.stage.change_own")
@require_POST
def api_stage_update(request):
    """Stage update from the management modal. Routes to the matching service so
    follow-up/meeting/frozen side-effects (reminders, notifications, audit,
    history) all happen server-side — no business logic here."""
    try:
        data = json.loads(request.body.decode() or "{}")
    except ValueError:
        return _err("Malformed request.")

    lead_id = data.get("lead_id")
    if not lead_id:
        return _err("Missing lead.")
    # Confirm the lead is visible to this user under their company scope.
    from .models import Lead
    try:
        lead = Lead.objects.select_related("current_stage").get(id=lead_id, company=request.company)
    except Lead.DoesNotExist:
        return _err("Lead not found.", status=404)

    stage = (data.get("stage_code") or "").upper()
    if stage == StageCode.FRESH:
        return _err("Sales cannot manually change lead stage back to Fresh.")
    if lead.current_stage and lead.current_stage.code == StageCode.INTERESTED and stage == StageCode.INTERESTED:
        return _err("Lead is already in Interested stage.")
    feedback = (data.get("feedback") or "").strip()
    meta = getattr(request, "request_meta", None)
    try:
        if stage == StageCode.FOLLOW_UP:
            FollowUpService.schedule(
                lead_id=lead_id,
                scheduled_at=_combine(data.get("reminder_date"), data.get("reminder_time")),
                actor=request.user, notes=feedback, request_meta=meta,
            )
        elif stage == StageCode.MEETING:
            MeetingService.schedule(
                lead_id=lead_id,
                scheduled_start=_combine(data.get("meeting_date"), data.get("meeting_time")),
                location=(data.get("meeting_location") or "").strip(),
                actor=request.user, request_meta=meta,
            )
        elif stage == StageCode.FROZEN:
            days = int(data.get("frozen_days") or 0)
            if days < 1:
                return _err("Enter the call-back period in days.")
            LeadStageService.freeze(
                lead_id=lead_id, days=days, actor=request.user,
                reason=feedback, request_meta=meta,
            )
        elif stage == StageCode.NOT_INTERESTED:
            reason = (data.get("reason") or "").strip()
            if not reason:
                return _err("A reason is required for Not Interested.")
            note = f"{reason}: {feedback}" if feedback else reason
            LeadStageService.change_stage(
                lead_id=lead_id, to_stage_code=stage, actor=request.user,
                reason=note, request_meta=meta,
            )
        elif stage == StageCode.NOT_REACHED:
            from apps.policies.constants import PolicyCode
            from apps.policies.services import PolicyResolver

            mode = PolicyResolver.option_code(
                request.company, PolicyCode.NOT_REACHED_REMINDER_MODE, default="AUTOMATIC"
            )
            scheduled_time = None
            if mode == "MANUAL":
                r_date = data.get("reminder_date")
                r_time = data.get("reminder_time")
                if r_date:
                    scheduled_time = _combine(r_date, r_time)
                else:
                    raise ValidationError("Reminder date is required for manual reminder mode.")

            LeadStageService.change_stage(
                lead_id=lead_id, to_stage_code=stage, actor=request.user,
                reason=feedback, request_meta=meta, scheduled_time=scheduled_time,
            )
        else:
            LeadStageService.change_stage(
                lead_id=lead_id, to_stage_code=stage, actor=request.user,
                reason=feedback, request_meta=meta,
            )
    except ValidationError as exc:
        return _err(exc, status=400)
    except PermissionDenied as exc:
        return _err(exc, status=403)
    return JsonResponse({"ok": True})


# ── Admin "All Leads" database page (all_leads.html) ──────────────────────────

@login_required
@crm_permission_required("leads.lead.view_all", "leads.lead.view_own")
@require_GET
def api_all_leads(request):
    """Leads for the All-Leads table, shaped with assignment / team / created-by
    columns. leads_for_user scopes by the caller's view permission, so a broker
    with only view_own gets just their own leads."""
    from apps.reports.selectors import leads_for_user

    leads_list = list(leads_for_user(request.user, request.company).select_related("created_by"))
    return JsonResponse({"leads": LeadSerializationService.rows(leads_list, admin=True)})


@login_required
@crm_permission_required("leads.lead.view_all", "leads.lead.view_own")
@require_GET
def api_all_lead_history(request):
    """Timeline for one lead (All-Leads page). Scoped to leads the caller may
    view, so a broker can only see history of their own leads."""
    from apps.reports.selectors import leads_for_user
    from .selectors import lead_detail_qs

    lead_id = request.GET.get("lead_id")
    allowed = leads_for_user(request.user, request.company).filter(
        id=lead_id
    ).exists()
    if not allowed:
        return _err("Lead not found.", status=404)
    lead = lead_detail_qs().filter(id=lead_id, company=request.company).first()
    if lead is None:
        return _err("Lead not found.", status=404)
    return JsonResponse({"history": LeadSerializationService.history(lead)})


@login_required
@crm_permission_required("leads.lead.deactivate")
@require_POST
def api_lead_set_active(request):
    """Activate / deactivate a lead (admin control). Routes through
    LeadAdminService so SLA cancel, audit and notification happen server-side."""
    from .models import Lead
    from .services import LeadAdminService

    try:
        data = json.loads(request.body.decode() or "{}")
    except ValueError:
        return _err("Malformed request.")
    lead_id = data.get("lead_id")
    if not lead_id or not Lead.objects.filter(
        id=lead_id, company=request.company
    ).exists():
        return _err("Lead not found.", status=404)
    try:
        LeadAdminService.set_active(
            lead_id=lead_id, active=bool(data.get("active")),
            reason=(data.get("reason") or "").strip(), actor=request.user,
            request_meta=getattr(request, "request_meta", None),
        )
    except ValidationError as exc:
        return _err(exc, status=400)
    return JsonResponse({"ok": True})


@login_required
@crm_permission_required("leads.lead.edit_all")
@require_POST
def api_lead_edit(request):
    """Edit a lead's contact fields + note (admin). Stage and salesman changes
    are delegated to LeadStageService / ManualAssignmentService."""
    from .models import Lead
    from .services import LeadAdminService

    try:
        data = json.loads(request.body.decode() or "{}")
    except ValueError:
        return _err("Malformed request.")
    try:
        lead = Lead.objects.select_related("current_stage").get(
            id=data.get("lead_id"), company=request.company
        )
    except Lead.DoesNotExist:
        return _err("Lead not found.", status=404)

    name = (data.get("name") or "").strip()
    if not name:
        return _err("Name is required.")
    try:
        LeadAdminService.edit(
            lead=lead, name=name, phone=(data.get("phone") or "").strip(),
            note=(data.get("note") or "").strip(),
            salesman_id=data.get("salesman_id") or "",
            stage_code=(data.get("stage_code") or "").upper(),
            actor=request.user, request_meta=getattr(request, "request_meta", None),
        )
    except ValidationError as exc:
        return _err(exc, status=400)
    except PermissionDenied as exc:
        return _err(exc, status=403)
    return JsonResponse({"ok": True})


# ── Manual distribution board (manual_distribution.html) ──────────────────────
#
# Two scopes, enforced server-side on every endpoint (leads spec §8.1):
#   leads.distribution.manual_all  → any salesman / sales head, all company leads
#   leads.distribution.team_manual → a sales head: only their own team members
#                                    (or self), only their team's leads

@login_required
@require_GET
def api_manual_dist_leads(request):
    """Leads visible on the manual board, shaped for the table."""
    if not ManualDistributionService.can_access(request.user):
        return _err("Forbidden.", status=403)
    leads_list = list(ManualDistributionService.leads(request.user, request.company))
    return JsonResponse({"leads": LeadSerializationService.rows(
        leads_list, assignment=True)})


@login_required
@require_GET
def api_manual_dist_salesmen(request):
    """Salesmen the user may assign to, with their active lead count (scoped)."""
    if not ManualDistributionService.can_access(request.user):
        return _err("Forbidden.", status=403)
    return JsonResponse({"salesmen": ManualDistributionService.salesmen_with_loads(
        request.user, request.company)})


@login_required
@require_GET
def api_manual_dist_history(request):
    """Timeline for one lead the user may distribute."""
    if not ManualDistributionService.can_access(request.user):
        return _err("Forbidden.", status=403)
    from .selectors import lead_detail_qs

    lead = lead_detail_qs().filter(
        id=request.GET.get("lead_id"), company=request.company
    ).first()
    if lead is None or not ManualDistributionService.leads(
        request.user, request.company
    ).filter(id=lead.id).exists():
        return _err("Lead not found.", status=404)
    return JsonResponse({"history": LeadSerializationService.history(lead)})


@login_required
@require_POST
def api_manual_dist_assign(request):
    """Assign a lead to a salesman. Routes through ManualAssignmentService so SLA
    reset, assignment history, audit and notification happen server-side."""
    if not ManualDistributionService.can_access(request.user):
        return _err("Forbidden.", status=403)
    from apps.distribution.services import ManualAssignmentService

    try:
        data = json.loads(request.body.decode() or "{}")
    except ValueError:
        return _err("Malformed request.")
    lead = ManualDistributionService.leads(request.user, request.company).filter(
        id=data.get("lead_id")
    ).first()
    if lead is None:
        return _err("Lead not found.", status=404)
    # SECURITY: re-validate the chosen salesman is within the user's allowed scope.
    pair = ManualDistributionService.resolve_assignee(
        request.user, request.company, data.get("salesman_id"))
    if pair is None:
        return _err("You can't assign to this salesman.", status=403)
    salesman, team = pair
    try:
        ManualAssignmentService.assign_to_salesman(
            lead_id=lead.id, salesman=salesman, team=team, actor=request.user,
            reason=(data.get("note") or "").strip() or "Manual distribution",
            request_meta=getattr(request, "request_meta", None),
        )
    except ValidationError as exc:
        return _err(exc, status=400)
    except PermissionDenied as exc:
        return _err(exc, status=403)
    return JsonResponse({"ok": True})


@require_GET
def api_salesman_leads(request, email=None):
    """External read-only API: list a salesman's leads (Bearer / x-api-key auth).

    GET /t/<slug>/api/leads/<email>  or  /t/<slug>/api/leads/?email=<email>
    request.company is resolved from the tenant DB by middleware; auth and the
    query live in LeadApiService (view stays thin)."""
    email = email or request.GET.get("email", "")
    try:
        LeadApiService.authenticate(request, getattr(request, "company", None))
    except PermissionDenied as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=401)
    if not email:
        return JsonResponse(
            {"success": False, "error": "email is required."}, status=400)

    rows, page = LeadApiService.leads_for_salesman(
        request.company, email, request.GET.get("page"))

    next_page_url = None
    if page.has_next():
        params = request.GET.copy()
        params["page"] = page.next_page_number()
        next_page_url = request.build_absolute_uri(
            f"{request.path}?{params.urlencode()}")

    return JsonResponse(
        {"success": True, "leads": rows, "next_page_url": next_page_url})
