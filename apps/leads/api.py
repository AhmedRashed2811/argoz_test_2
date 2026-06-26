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

from apps.accounts.models import Language, Team, User
from apps.authorization.decorators import crm_permission_required
from apps.authorization.services import EffectivePermissionResolver
from apps.core.exceptions import PermissionDenied, ValidationError
from apps.distribution.selectors import eligible_pool

from .constants import ActiveStatus, SourceCode, StageCode
from .services import (
    DuplicateService,
    FollowUpService,
    LeadStageService,
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
    is_broker = (
        request.user.broker_profile.filter(company=request.company).exists()
        if hasattr(request.user, "broker_profile") else False
    )
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
        "sources": allowed, "is_broker": is_broker, "is_head": is_head,
        "is_salesman": is_salesman, "can_manual": can_manual,
        "head_assignment": head_assignment,
        "broker_also_assign_salesman": broker_also_assign_salesman,
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
    from .models import Client

    phone = (request.GET.get("phone") or "").strip()
    client = (
        Client.objects.filter(company=request.company, phone=phone)
        .select_related("original_salesman").first()
        if phone else None
    )
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
    from apps.marketing.models import Campaign
    from apps.marketing.selectors import campaign_available_channels

    campaign = Campaign.objects.filter(
        pk=request.GET.get("campaign"), company=request.company
    ).first()
    if campaign is None:
        return _err("Unknown campaign.")
    return JsonResponse({"channels": campaign_available_channels(campaign)})


@login_required
@require_GET
def api_campaign_children(request):
    from apps.marketing.models import Campaign
    from apps.marketing.selectors import channel_records

    campaign = Campaign.objects.filter(
        pk=request.GET.get("campaign"), company=request.company
    ).first()
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
    from apps.leads.services.walkin_service import (
        FULL_ROTATION, ROT_FULL, ROT_TEAM, TEAM_TURN, WalkInService,
    )

    policy = PolicyResolver.option_code(
        request.company, PolicyCode.WALKIN_RECEPTION_POLICY, default="OPEN_FLOOR")
    if policy == FULL_ROTATION:
        WalkInService.advance_pointer(
            request.company, ROT_FULL, len(WalkInService.available_members(request.company)))
    elif policy == TEAM_TURN:
        from apps.accounts.models import Team
        WalkInService.advance_pointer(
            request.company, ROT_TEAM,
            Team.objects.filter(company=request.company, is_active=True).count())
    return JsonResponse(WalkInService.rotation_state(request.company, policy))


@login_required
@require_GET
def api_brokers(request):
    from apps.accounts.models import Broker, BrokerStatus

    return JsonResponse({"brokers": [
        {"id": str(b.id), "name": b.name}
        for b in Broker.objects.filter(
            company=request.company, status=BrokerStatus.ACTIVE
        ).order_by("name")
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
    teams = Team.objects.filter(company=request.company, sales_head=request.user)
    pool = [m for t in teams for m in t.members.select_related("user", "team")
            if m.user.is_active]
    return JsonResponse({"members": _people(pool)})


@login_required
@require_GET
def api_teams(request):
    return JsonResponse({"teams": [
        {"id": str(t.id), "name": t.name}
        for t in Team.objects.filter(company=request.company, is_active=True)
        .order_by("order_index", "name")
    ]})


@login_required
@require_GET
def api_cc_agents(request):
    """Users permitted to capture call-center leads (§4.2g)."""
    users = User.objects.filter(
        is_active=True, profile__company=request.company
    ).select_related("profile")
    agents = [
        {"id": str(u.id), "name": u.get_full_name() or u.email}
        for u in users
        if EffectivePermissionResolver.has(u, "leads.lead.create_from_call_center")
    ]
    return JsonResponse({"agents": agents})


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
    pool = eligible_pool(company=request.company)
    teams = Team.objects.filter(
        company=request.company, is_active=True
    ).order_by("order_index", "name")
    return JsonResponse({
        "policy": policy,
        "rotation_order": _people(pool),
        "teams": [{"id": str(t.id), "name": t.name} for t in teams],
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

    return JsonResponse({
        "ok": True, "lead_id": str(lead.id),
        "redirect": reverse("leads:detail", args=[lead.id]),
    })


# ── Sales-leads management page (lead_list.html) ──────────────────────────────

def _ms(dt):
    """Datetime -> epoch milliseconds (JS-friendly), or None."""
    return int(dt.timestamp() * 1000) if dt else None


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
    from apps.marketing.models import EventRecord, TVAdRecord, StreetAdRecord, ExhibitionRecord, SocialMediaAdRecord

    leads_list = list(leads_for_user(request.user, request.company))
    child_ids = [l.campaign_child_id for l in leads_list if l.campaign_child_id]
    names_dict = {}

    if child_ids:
        for pk, name in EventRecord.objects.filter(id__in=child_ids).values_list("id", "name"):
            names_dict[str(pk)] = name
        for pk, name in TVAdRecord.objects.filter(id__in=child_ids).values_list("id", "name"):
            names_dict[str(pk)] = name
        for pk, name in StreetAdRecord.objects.filter(id__in=child_ids).values_list("id", "name"):
            names_dict[str(pk)] = name
        for pk, name in SocialMediaAdRecord.objects.filter(id__in=child_ids).values_list("id", "name"):
            names_dict[str(pk)] = name
        for pk, name in ExhibitionRecord.objects.filter(id__in=child_ids).values_list("id", "name"):
            names_dict[str(pk)] = name

    out = []
    for l in leads_list:
        out.append({
            "id": str(l.id),
            "name": l.name,
            "phone": l.phone,
            "source": l.source.name if l.source_id else "",
            "specificSource": names_dict.get(str(l.campaign_child_id), "") if l.campaign_child_id else "",
            "campaign": l.campaign.name if l.campaign_id else "",
            "campaign_child_type": l.campaign_child_type,
            "broker": l.broker_owner.name if l.broker_owner_id else "",
            "stage": l.current_stage.name if l.current_stage_id else "Fresh",
            "active": l.active_status == ActiveStatus.ACTIVE,
            "createdAt": _ms(l.created_at),
            "updatedAt": _ms(l.updated_at),
            "slaDeadline": _ms(l.sla_deadline),
        })
    return JsonResponse({"leads": out})


def _actor_name(user):
    """Display name of the user who performed an action (not the lead owner)."""
    if user is None:
        return None
    return user.get_full_name() or user.email


def _lead_history_items(lead):
    """Build the timeline for one lead from stage / assignment / follow-up /
    meeting / note records. Shared by the sales and admin history endpoints.
    Each item carries `by` = the actor who performed it."""
    items = [{
        "type": "created", "ts": _ms(lead.created_at), "label": "Lead Created",
        "feedback": "Lead added to the system.", "by": _actor_name(lead.created_by),
    }]
    for h in lead.stage_history.all():
        if h.from_stage_id == h.to_stage_id:
            continue
        to_name = h.to_stage.name if h.to_stage_id else ""
        clean_reason = h.reason
        if clean_reason and "By Turn index" in clean_reason:
            clean_reason = "By Turn Rotation"
        items.append({
            "type": "stage", "ts": _ms(h.changed_at),
            "label": f"Stage changed to {to_name}", "feedback": clean_reason or None,
            "by": _actor_name(h.actor),
        })
    for a in lead.assignment_history.all():
        from_name = a.from_salesman.get_full_name() or a.from_salesman.email if a.from_salesman else None
        to_name = a.to_salesman.get_full_name() or a.to_salesman.email if a.to_salesman else None
        
        clean_reason = a.reason
        if clean_reason and "By Turn index" in clean_reason:
            clean_reason = "By Turn Rotation"
            
        if from_name and from_name != to_name:
            label = f"Reassigned from {from_name} to {to_name}"
        else:
            label = f"Assigned to {to_name}"
            
        from .constants import AssignmentMethod
        auto = a.assignment_method != AssignmentMethod.MANUAL
        items.append({
            "type": "assignment",
            "ts": _ms(a.assigned_at),
            "label": label,
            "feedback": clean_reason or None,
            "by": "System" if auto else _actor_name(a.actor),
        })
    for f in lead.followups.all():
        d = timezone.localtime(f.scheduled_at)
        items.append({
            "type": "followup", "ts": _ms(f.created_at),
            "label": f"Follow-up scheduled for {d.date().isoformat()}",
            "reminderDate": d.date().isoformat(), "reminderTime": d.strftime("%H:%M"),
            "feedback": f.notes or None, "by": _actor_name(f.created_by),
        })
    for m in lead.meetings.all():
        d = timezone.localtime(m.scheduled_start)
        items.append({
            "type": "meeting", "ts": _ms(m.created_at),
            "label": f"Meeting scheduled for {d.date().isoformat()}",
            "meetingDate": d.date().isoformat(), "meetingTime": d.strftime("%H:%M"),
            "meetingLocation": m.location or None, "by": _actor_name(m.created_by),
        })
    for n in lead.lead_notes.all():
        if n.is_deleted:
            continue
        items.append({"type": "note", "ts": _ms(n.created_at),
                      "label": "Note added", "feedback": n.body,
                      "by": _actor_name(n.created_by)})

    items.sort(key=lambda i: i["ts"] or 0, reverse=True)
    return items


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
    return JsonResponse({"history": _lead_history_items(lead)})


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

def _campaign_child_names(leads_list):
    """Resolve campaign_child_id -> record name across marketing record tables."""
    from apps.marketing.models import (
        EventRecord, ExhibitionRecord, SocialMediaAdRecord, StreetAdRecord,
        TVAdRecord,
    )

    child_ids = [l.campaign_child_id for l in leads_list if l.campaign_child_id]
    names = {}
    if child_ids:
        for model in (EventRecord, TVAdRecord, StreetAdRecord,
                      SocialMediaAdRecord, ExhibitionRecord):
            for pk, name in model.objects.filter(
                id__in=child_ids
            ).values_list("id", "name"):
                names[str(pk)] = name
    return names


@login_required
@crm_permission_required("leads.lead.view_all")
@require_GET
def api_all_leads(request):
    """Every lead in the company (admin database view, leads.lead.view_all),
    shaped for the All-Leads table with assignment / team / created-by columns."""
    from apps.reports.selectors import leads_for_user

    leads_list = list(leads_for_user(request.user, request.company).select_related("created_by"))
    names = _campaign_child_names(leads_list)
    out = []
    for l in leads_list:
        sm = l.assigned_salesman
        out.append({
            "id": str(l.id),
            "name": l.name,
            "phone": l.phone,
            "source": l.source.name if l.source_id else "",
            "specificSource": names.get(str(l.campaign_child_id), "") if l.campaign_child_id else "",
            "campaign": l.campaign.name if l.campaign_id else "",
            "campaign_child_type": l.campaign_child_type,
            "broker": l.broker_owner.name if l.broker_owner_id else "",
            "stage": l.current_stage.name if l.current_stage_id else "Fresh",
            "active": l.active_status == ActiveStatus.ACTIVE,
            "createdAt": _ms(l.created_at),
            "updatedAt": _ms(l.updated_at),
            "slaDeadline": _ms(l.sla_deadline),
            "assignedTo": (sm.get_full_name() or sm.email) if sm else "",
            "assignedToId": str(l.assigned_salesman_id) if l.assigned_salesman_id else "",
            "createdBy": (l.created_by.get_full_name() or l.created_by.email) if l.created_by_id else "",
            "team": l.assigned_team.name if l.assigned_team_id else "",
            "lifecycle": (l.metadata or {}).get("lifecycle", "New"),
        })
    return JsonResponse({"leads": out})


@login_required
@crm_permission_required("leads.lead.view_all")
@require_GET
def api_all_lead_history(request):
    """Timeline for one lead (admin All-Leads page)."""
    from .selectors import lead_detail_qs

    lead = lead_detail_qs().filter(
        id=request.GET.get("lead_id"), company=request.company
    ).first()
    if lead is None:
        return _err("Lead not found.", status=404)
    return JsonResponse({"history": _lead_history_items(lead)})


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
    from apps.accounts.models import User
    from apps.distribution.services import ManualAssignmentService
    from .models import Lead
    from .services import LeadAdminService

    try:
        data = json.loads(request.body.decode() or "{}")
    except ValueError:
        return _err("Malformed request.")
    lead_id = data.get("lead_id")
    try:
        lead = Lead.objects.select_related("current_stage").get(
            id=lead_id, company=request.company
        )
    except Lead.DoesNotExist:
        return _err("Lead not found.", status=404)

    name = (data.get("name") or "").strip()
    if not name:
        return _err("Name is required.")
    meta = getattr(request, "request_meta", None)
    try:
        LeadAdminService.update_basic(
            lead_id=lead_id, name=name, phone=(data.get("phone") or "").strip(),
            note=(data.get("note") or "").strip(), actor=request.user,
            request_meta=meta,
        )
        # Reassignment, when a different salesman was picked.
        salesman_id = data.get("salesman_id") or ""
        if salesman_id and str(lead.assigned_salesman_id) != salesman_id:
            salesman = User.objects.filter(
                id=salesman_id, profile__company=request.company, is_active=True
            ).first()
            if salesman is None:
                return _err("Unknown salesman.")
            # Move the lead to the new salesman's team (membership in this company).
            membership = salesman.team_memberships.filter(
                team__company=request.company, team__is_active=True
            ).select_related("team").first()
            ManualAssignmentService.assign_to_salesman(
                lead_id=lead_id, salesman=salesman,
                team=membership.team if membership else None,
                actor=request.user, reason="Edited via All Leads", request_meta=meta,
            )
        # Stage change, when a different stage was picked.
        stage_code = (data.get("stage_code") or "").upper()
        if stage_code and (lead.current_stage is None
                           or lead.current_stage.code != stage_code):
            LeadStageService.change_stage(
                lead_id=lead_id, to_stage_code=stage_code, actor=request.user,
                reason="Edited via All Leads", request_meta=meta,
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

def _manual_guard(user):
    return any(
        EffectivePermissionResolver.has(user, c)
        for c in ("leads.distribution.manual_all", "leads.distribution.team_manual")
    )


def _manual_scope(user, company):
    """('all', None) | ('team', [team_ids]) | (None, None). manual_all wins."""
    if EffectivePermissionResolver.has(user, "leads.distribution.manual_all"):
        return "all", None
    if EffectivePermissionResolver.has(user, "leads.distribution.team_manual"):
        team_ids = list(Team.objects.filter(
            company=company, sales_head=user, is_active=True
        ).values_list("id", flat=True))
        return "team", team_ids
    return None, None


def _manual_leads_qs(user, company):
    """Leads awaiting manual distribution that the user may handle (docs §8.1).

    A lead needs manual distribution exactly when it is active but has no
    salesman — the state every escalation path leaves it in (empty eligible
    pool, broker→MANUAL, TEAM_HEAD_DECIDES, SLA-expiry MANUAL). Scope:
      manual_all  → all such leads company-wide;
      team_manual → those already routed to a team this user heads (the head
                    picks the salesman)."""
    from .models import Lead

    scope, team_ids = _manual_scope(user, company)
    base = Lead.objects.filter(
        company=company,
        active_status=ActiveStatus.ACTIVE,
        assigned_salesman__isnull=True,
    ).select_related(
        "source", "current_stage", "assigned_salesman", "assigned_team",
        "campaign", "broker_owner",
    )
    if scope == "all":
        return base
    if scope == "team":
        return base.filter(assigned_team_id__in=team_ids)
    return base.none()


def _assignable_people(user, company):
    """[(user, team)] the user may assign to, de-duplicated. manual_all → every
    active salesman + sales head; team_manual → the head's own team members + self."""
    scope, team_ids = _manual_scope(user, company)
    if scope == "all":
        teams = Team.objects.filter(company=company, is_active=True)
    elif scope == "team":
        teams = Team.objects.filter(id__in=team_ids)
    else:
        return []
    teams = teams.select_related("sales_head").prefetch_related(
        "members__user", "members__team")
    seen, out = set(), []
    for t in teams:
        for m in t.members.all():
            if m.user.is_active and m.user_id not in seen:
                seen.add(m.user_id)
                out.append((m.user, t))
        head = t.sales_head
        if head and head.is_active and head.id not in seen:
            seen.add(head.id)
            out.append((head, t))
    return out


@login_required
@require_GET
def api_manual_dist_leads(request):
    """Leads visible on the manual board, shaped for the table."""
    if not _manual_guard(request.user):
        return _err("Forbidden.", status=403)
    leads_list = list(_manual_leads_qs(request.user, request.company))
    names = _campaign_child_names(leads_list)
    out = []
    for l in leads_list:
        sm = l.assigned_salesman
        out.append({
            "id": str(l.id),
            "name": l.name,
            "phone": l.phone,
            "source": l.source.name if l.source_id else "",
            "specificSource": names.get(str(l.campaign_child_id), "") if l.campaign_child_id else "",
            "campaign": l.campaign.name if l.campaign_id else "",
            "campaign_child_type": l.campaign_child_type,
            "broker": l.broker_owner.name if l.broker_owner_id else "",
            "stage": l.current_stage.name if l.current_stage_id else "Fresh",
            "active": l.active_status == ActiveStatus.ACTIVE,
            "createdAt": _ms(l.created_at),
            "updatedAt": _ms(l.updated_at),
            "slaDeadline": _ms(l.sla_deadline),
            "assignedTo": (sm.get_full_name() or sm.email) if sm else "",
            "assignedToId": str(l.assigned_salesman_id) if l.assigned_salesman_id else "",
            "team": l.assigned_team.name if l.assigned_team_id else "",
        })
    return JsonResponse({"leads": out})


@login_required
@require_GET
def api_manual_dist_salesmen(request):
    """Salesmen the user may assign to, with their active lead count (scoped)."""
    if not _manual_guard(request.user):
        return _err("Forbidden.", status=403)
    from apps.distribution.selectors import batch_candidate_loads

    people = _assignable_people(request.user, request.company)
    loads = batch_candidate_loads([u for u, _ in people], request.company)
    out = []
    for u, team in people:
        active, _last = loads.get(u.id, (0, None))
        out.append({
            "id": str(u.id), "name": u.get_full_name() or u.email,
            "team": team.name, "team_id": str(team.id), "count": active,
        })
    return JsonResponse({"salesmen": out})


@login_required
@require_GET
def api_manual_dist_history(request):
    """Timeline for one lead the user may distribute."""
    if not _manual_guard(request.user):
        return _err("Forbidden.", status=403)
    from .selectors import lead_detail_qs

    lead = lead_detail_qs().filter(
        id=request.GET.get("lead_id"), company=request.company
    ).first()
    if lead is None or not _manual_leads_qs(
        request.user, request.company
    ).filter(id=lead.id).exists():
        return _err("Lead not found.", status=404)
    return JsonResponse({"history": _lead_history_items(lead)})


@login_required
@require_POST
def api_manual_dist_assign(request):
    """Assign a lead to a salesman. Routes through ManualAssignmentService so SLA
    reset, assignment history, audit and notification happen server-side."""
    if not _manual_guard(request.user):
        return _err("Forbidden.", status=403)
    from apps.distribution.services import ManualAssignmentService

    try:
        data = json.loads(request.body.decode() or "{}")
    except ValueError:
        return _err("Malformed request.")
    lead = _manual_leads_qs(request.user, request.company).filter(
        id=data.get("lead_id")
    ).first()
    if lead is None:
        return _err("Lead not found.", status=404)
    # SECURITY: re-validate the chosen salesman is within the user's allowed scope.
    allowed = {
        str(u.id): (u, team)
        for u, team in _assignable_people(request.user, request.company)
    }
    pair = allowed.get(data.get("salesman_id") or "")
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
