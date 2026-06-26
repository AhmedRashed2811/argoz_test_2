"""AJAX/JSON endpoints for the dynamic lead-creation page (leads spec §4).
Thin: permission check -> selector/service -> JSON. No business logic here;
creation routes through SourceRouterService."""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import Language, Team, User
from apps.authorization.services import EffectivePermissionResolver
from apps.core.exceptions import PermissionDenied, ValidationError
from apps.distribution.selectors import eligible_pool

from .constants import SourceCode
from .services import DuplicateService, SourceRouterService

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
    return JsonResponse({
        "sources": allowed, "is_broker": is_broker, "is_head": is_head,
        "is_salesman": is_salesman, "can_manual": can_manual,
        "head_assignment": head_assignment,
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
