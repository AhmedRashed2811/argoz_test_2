"""Per-source lead creation routing (leads spec §4.2). Owns the source-specific
assignment rules and re-derives the actor's capability from the permission layer
(never trusts a client-sent role). All writes are delegated to the existing
services (LeadCreationService / WalkInService / ExistingClientService) so source
rules, duplicate handling, SLA, audit, attribution and distribution stay in one
place. Thin views call SourceRouterService.create_lead(...)."""
from __future__ import annotations

from django.db import transaction

from apps.accounts.models import Broker, Team, User
from apps.authorization.services import EffectivePermissionResolver
from apps.core.exceptions import PermissionDenied, ValidationError
from apps.marketing.constants import ChannelType
from apps.policies.constants import PolicyCode
from apps.policies.services import PolicyResolver

from ..constants import Origin, SourceCode
from .existing_client_service import ExistingClientService
from .lead_creation_service import LeadCreationService
from .walkin_service import WalkInService

# Form channel value -> ChannelType code (campaign child / how-did-you-know).
_CHANNEL_MAP = {
    "event": ChannelType.EVENT,
    "tv_ad": ChannelType.TV_AD,
    "street_ad": ChannelType.STREET_AD,
    "social_media_ad": ChannelType.SOCIAL_MEDIA_AD,
    "exhibition": ChannelType.EXHIBITION,
}

_MANUAL_ASSIGN_CODES = (
    "leads.distribution.manual_all",
    "leads.distribution.team_manual",
)


class SourceRouterService:
    @staticmethod
    @transaction.atomic
    def create_lead(*, company, actor, source_code, data, request_meta=None):
        """data is a plain dict of cleaned form values. Returns the created Lead."""
        print(f"\n[SourceRouterService] create_lead: source={source_code}, actor={actor}, data={data}")
        if source_code not in SourceCode.ALL:
            raise ValidationError("Unknown lead source.")
        # §4.2b: a user may only create from sources they are permitted to.
        perm = f"leads.lead.create_from_{source_code.lower()}"
        if not EffectivePermissionResolver.has(actor, perm):
            raise PermissionDenied(f"Not allowed to create {source_code} leads.")

        handler = getattr(SourceRouterService, f"_{source_code.lower()}")
        return handler(company=company, actor=actor, data=data,
                       request_meta=request_meta)

    # ---- shared helpers ---------------------------------------------------
    @staticmethod
    def _base_kwargs(company, actor, source_code, data, request_meta):
        return dict(
            company=company, actor=actor, source_code=source_code,
            request_meta=request_meta,
            name=data.get("name", ""), phone=data.get("phone", ""),
            email=data.get("email", ""), country_code=data.get("country_code", ""),
            language=data.get("language"),
            origin=Origin.BROKER if source_code == SourceCode.BROKER else Origin.DIRECT,
            metadata={"notes": data.get("notes", "")} if data.get("notes") else None,
        )

    @staticmethod
    def _can_manual_assign(actor):
        return any(EffectivePermissionResolver.has(actor, c) for c in _MANUAL_ASSIGN_CODES)

    @staticmethod
    def _salesman(company, salesman_id):
        if not salesman_id:
            raise ValidationError("Select a salesman to assign.")
        sm = User.objects.filter(
            pk=salesman_id, is_active=True, profile__company=company
        ).first()
        if sm is None:
            raise ValidationError("Selected salesman is not valid.")
        return sm

    @staticmethod
    def _team(company, team_id):
        team = Team.objects.filter(pk=team_id, company=company, is_active=True).first()
        if team is None:
            raise ValidationError("Selected team is not valid.")
        return team

    @staticmethod
    def _marketing_attr(company, data, *, required=False):
        """Resolve a channel + record selection (Walk-in/Call Center/Exhibition)
        into (campaign, child_type, child_id, platform, event) for attribution +
        lead_count. Non-record channels (website/passing-by) attribute nothing."""
        from apps.marketing.constants import FE_TO_CHANNEL
        from apps.marketing.models import (
            EventRecord, ExhibitionRecord, SocialMediaAdRecord,
            SocialPlatformDefinition, StreetAdRecord, TVAdRecord,
        )

        ct = FE_TO_CHANNEL.get(data.get("channel"))
        if ct is None:
            if required:
                raise ValidationError("Select a valid channel.")
            return None, "", None, None, None
        platform = event = None
        if ct == ChannelType.SOCIAL_MEDIA_AD:
            platform = SocialPlatformDefinition.objects.filter(
                pk=data.get("social_platform_id")).first()
            rec = SocialMediaAdRecord.objects.filter(
                pk=data.get("social_ad_id") or data.get("record_id"),
                campaign__company=company).first()
            if rec:
                event = rec.linked_event
        else:
            model = {ChannelType.EVENT: EventRecord, ChannelType.TV_AD: TVAdRecord,
                     ChannelType.STREET_AD: StreetAdRecord,
                     ChannelType.EXHIBITION: ExhibitionRecord}[ct]
            rec = model.objects.filter(
                pk=data.get("record_id"), campaign__company=company).first()
            if ct == ChannelType.EVENT:
                event = rec
        if rec is None:
            raise ValidationError("Select the channel detail.")
        return rec.campaign, ct, str(rec.id), platform, event

    @staticmethod
    def _campaign_child(data):
        """Returns (campaign_child_type, campaign_child_id, platform, event)."""
        from apps.marketing.models import (
            EventRecord,
            SocialMediaAdRecord,
            SocialPlatformDefinition,
        )

        channel = _CHANNEL_MAP.get(data.get("channel"))
        if channel is None:
            raise ValidationError("Select a valid campaign channel.")
        platform = event = None
        child_id = data.get("child_id") or None
        if channel == ChannelType.SOCIAL_MEDIA_AD:
            platform = SocialPlatformDefinition.objects.filter(
                pk=data.get("social_platform_id")
            ).first()
            child_id = data.get("social_ad_id") or None
            if child_id:
                sad = SocialMediaAdRecord.objects.filter(pk=child_id).first()
                event = sad.linked_event if sad else None
        elif channel == ChannelType.EVENT and child_id:
            event = EventRecord.objects.filter(pk=child_id).first()
        if not child_id:
            raise ValidationError("Select the campaign channel detail.")
        return channel, child_id, platform, event

    # ---- per-source handlers ---------------------------------------------
    @staticmethod
    def _self_generated(*, company, actor, data, request_meta):
        print(f"[SourceRouterService] Routing self_generated lead: actor={actor}")
        base = SourceRouterService._base_kwargs(
            company, actor, SourceCode.SELF_GENERATED, data, request_meta
        )
        memberships = list(actor.team_memberships.filter(team__company=company)
                           .select_related("team"))
        is_head = Team.objects.filter(company=company, sales_head=actor).exists()

        # Salesman actor: auto-assigned to self (handled by LeadCreationService),
        # SLA keep-vs-redistribute follows the salesman policy (§4.2e).
        if memberships and not is_head:
            return LeadCreationService.create(**base)

        if is_head:
            mode = PolicyResolver.option_code(
                company, PolicyCode.SELF_GENERATED_HEAD_ASSIGNMENT,
                default="SELF_OR_MANUAL_TEAM",
            )
            assign = data.get("sg_assign", "self")
            head_teams = list(Team.objects.filter(company=company, sales_head=actor))
            if mode == "SELF_ONLY":
                return LeadCreationService.create(**base, assigned_salesman=actor,
                                                  auto_distribute=False)
            if mode == "AUTO_ROUND_ROBIN_TEAM" or assign == "rr":
                # Round-robin scoped to the head's own team(s).
                return LeadCreationService.create(
                    **base, auto_distribute=True, assigned_team=head_teams[0]
                    if head_teams else None,
                )
            if assign == "member":
                sm = SourceRouterService._salesman(company, data.get("sg_member_id"))
                if not actor_team_contains(head_teams, sm):
                    raise ValidationError("Salesman must be in your team.")
                return LeadCreationService.create(**base, assigned_salesman=sm,
                                                  auto_distribute=False)
            # default: assign to self
            return LeadCreationService.create(**base, assigned_salesman=actor,
                                              auto_distribute=False)
        # Not a salesman/head with a team — let the service validate/escalate.
        return LeadCreationService.create(**base, assigned_salesman=actor,
                                          auto_distribute=False)

    @staticmethod
    def _campaign(*, company, actor, data, request_meta):
        print(f"[SourceRouterService] Routing campaign lead: actor={actor}, campaign_id={data.get('campaign_id')}, dist={data.get('dist')}, assign_id={data.get('assign_id')}")
        from apps.marketing.models import Campaign

        campaign = Campaign.objects.filter(
            pk=data.get("campaign_id"), company=company
        ).first()
        if campaign is None:
            raise ValidationError("Select a valid campaign.")
        child_type, child_id, platform, event = SourceRouterService._campaign_child(data)
        base = SourceRouterService._base_kwargs(
            company, actor, SourceCode.CAMPAIGN, data, request_meta
        )
        kwargs = dict(**base, campaign=campaign, campaign_child_type=child_type,
                      campaign_child_id=child_id, attribution_platform=platform,
                      attribution_event=event)
        if data.get("dist") == "manual":
            if not SourceRouterService._can_manual_assign(actor):
                raise PermissionDenied("Not allowed to assign manually.")
            return SourceRouterService._with_manual_target(kwargs, company, data)
        return LeadCreationService.create(**kwargs, auto_distribute=True)

    @staticmethod
    def _broker(*, company, actor, data, request_meta):
        print(f"[SourceRouterService] Routing broker lead: actor={actor}, broker_id={data.get('broker_id')}, broker_policy={data.get('broker_policy')}, salesman_id={data.get('salesman_id')}")
        base = SourceRouterService._base_kwargs(
            company, actor, SourceCode.BROKER, data, request_meta
        )
        own_broker = Broker.objects.filter(company=company, linked_user=actor).first()
        if own_broker is not None:
            broker = own_broker
        else:
            broker = Broker.objects.filter(
                pk=data.get("broker_id"), company=company
            ).first()
            if broker is None:
                raise ValidationError("Select a broker.")
        also_salesman = bool(PolicyResolver.value(
            company, PolicyCode.BROKER_ALSO_ASSIGN_SALESMAN, default=False
        ))
        kwargs = dict(**base, broker_owner=broker)
        if also_salesman and data.get("broker_policy") == "salesman":
            sm = SourceRouterService._salesman(company, data.get("salesman_id"))
            return LeadCreationService.create(**kwargs, assigned_salesman=sm,
                                              auto_distribute=False)
        # Broker-only: no salesman assignment, no auto distribution (§8.5).
        return LeadCreationService.create(**kwargs, auto_distribute=False)

    @staticmethod
    def _walk_in(*, company, actor, data, request_meta):
        """Interactive reception (leads spec §4.2d). The receptionist's pick drives
        assignment; the company policy governs which rotation cursor advances."""
        print(f"[SourceRouterService] Routing walk_in lead: actor={actor}, channel={data.get('channel')}, salesman_id={data.get('salesman_id')}")
        from apps.distribution.services import ManualDistributionEscalation
        from apps.leads.models import WalkInQueueEntry
        from apps.leads.services.walkin_service import (
            FULL_ROTATION, ROT_FULL, ROT_TEAM, TEAM_TURN, WalkInService,
        )

        policy = PolicyResolver.option_code(
            company, PolicyCode.WALKIN_RECEPTION_POLICY, default="OPEN_FLOOR")
        campaign, ctype, cid, platform, event = SourceRouterService._marketing_attr(
            company, data)
        base = SourceRouterService._base_kwargs(
            company, actor, SourceCode.WALK_IN, data, request_meta)
        base["metadata"] = {"how_did_you_know": data.get("channel", ""),
                            "walkin_policy": policy, "notes": data.get("notes", "")}
        salesman = (SourceRouterService._salesman(company, data.get("salesman_id"))
                    if data.get("salesman_id") else None)
        lead = LeadCreationService.create(
            **base, assigned_salesman=salesman, auto_distribute=False,
            campaign=campaign, campaign_child_type=ctype, campaign_child_id=cid,
            attribution_platform=platform, attribution_event=event)
        entry = WalkInQueueEntry.objects.create(
            lead=lead, receptionist=actor, selected_policy_code=policy,
            assigned_salesman=salesman)
        if salesman is None:
            WalkInService._apply_policy(policy, lead, entry, actor, request_meta)
            lead.refresh_from_db()
        elif policy == FULL_ROTATION:
            # Served from the company-wide rotation -> cursor moves past this person.
            WalkInService.advance_pointer(
                company, ROT_FULL, len(WalkInService.available_members(company)))
        elif policy == TEAM_TURN:
            from apps.accounts.models import Team
            WalkInService.advance_pointer(
                company, ROT_TEAM,
                Team.objects.filter(company=company, is_active=True).count())
        return lead

    @staticmethod
    def _call_center(*, company, actor, data, request_meta):
        print(f"[SourceRouterService] Routing call_center lead: actor={actor}, cc_agent_id={data.get('cc_agent_id')}, dist={data.get('dist')}, salesman_id={data.get('salesman_id')}")
        base = SourceRouterService._base_kwargs(
            company, actor, SourceCode.CALL_CENTER, data, request_meta
        )
        # The agent who captured the lead: self, or a selected agent if the actor
        # is creating on someone else's behalf (§4.2g).
        agent_id = data.get("cc_agent_id")
        agent = (SourceRouterService._salesman(company, agent_id)
                 if agent_id and str(agent_id) != str(actor.pk) else actor)
        campaign, ctype, cid, platform, event = SourceRouterService._marketing_attr(
            company, data)
        kwargs = dict(**base, call_center_agent=agent, campaign=campaign,
                      campaign_child_type=ctype, campaign_child_id=cid,
                      attribution_platform=platform, attribution_event=event)
        if data.get("dist") == "manual":
            if not SourceRouterService._can_manual_assign(actor):
                raise PermissionDenied("Not allowed to assign manually.")
            sm = SourceRouterService._salesman(company, data.get("salesman_id"))
            return LeadCreationService.create(**kwargs, assigned_salesman=sm,
                                              auto_distribute=False)
        return LeadCreationService.create(**kwargs, auto_distribute=True)

    @staticmethod
    def _exhibition(*, company, actor, data, request_meta):
        print(f"[SourceRouterService] Routing exhibition lead: actor={actor}, salesman_id={data.get('salesman_id')}")
        base = SourceRouterService._base_kwargs(
            company, actor, SourceCode.EXHIBITION, data, request_meta
        )
        # Exhibition: pick the exhibition record (attribution + lead_count) and a
        # salesman (source.requires_salesman).
        data["channel"] = "exhibition"
        campaign, ctype, cid, platform, event = SourceRouterService._marketing_attr(
            company, data, required=True)
        sm = SourceRouterService._salesman(company, data.get("salesman_id"))
        return LeadCreationService.create(
            **base, assigned_salesman=sm, auto_distribute=False,
            campaign=campaign, campaign_child_type=ctype, campaign_child_id=cid,
            attribution_platform=platform, attribution_event=event)

    @staticmethod
    def _referral(*, company, actor, data, request_meta):
        print(f"[SourceRouterService] Routing referral lead: actor={actor}, dist={data.get('dist')}, salesman_id={data.get('salesman_id')}")
        base = SourceRouterService._base_kwargs(
            company, actor, SourceCode.REFERRAL, data, request_meta
        )
        kwargs = dict(**base, referrer_name=data.get("referrer_name", ""))
        if data.get("dist") == "manual":
            if not SourceRouterService._can_manual_assign(actor):
                raise PermissionDenied("Not allowed to assign manually.")
            sm = SourceRouterService._salesman(company, data.get("salesman_id"))
            return LeadCreationService.create(**kwargs, assigned_salesman=sm,
                                              auto_distribute=False)
        return LeadCreationService.create(**kwargs, auto_distribute=True)

    @staticmethod
    def _existing_client(*, company, actor, data, request_meta):
        print(f"[SourceRouterService] Routing existing_client lead: actor={actor}, phone={data.get('phone')}")
        # ExistingClientService applies the preserve/redistribute policy and
        # LeadCreationService escalates active in-SLA duplicates to manual (§4.2f).
        return ExistingClientService.create_from_client(
            company=company, name=data.get("name", ""), phone=data.get("phone", ""),
            actor=actor, email=data.get("email", ""),
            country_code=data.get("country_code", ""), language=data.get("language"),
            request_meta=request_meta,
        )

    # ---- manual-target resolution for campaign (team or salesman) ----------
    @staticmethod
    def _with_manual_target(kwargs, company, data):
        target = data.get("assign_id") or ""
        if target.startswith("team:"):
            team = SourceRouterService._team(company, target.split(":", 1)[1])
            return LeadCreationService.create(**kwargs, assigned_team=team,
                                              auto_distribute=False)
        sm = SourceRouterService._salesman(company, data.get("salesman_id") or target)
        return LeadCreationService.create(**kwargs, assigned_salesman=sm,
                                          auto_distribute=False)


def actor_team_contains(teams, salesman) -> bool:
    team_ids = {t.id for t in teams}
    return salesman.team_memberships.filter(team_id__in=team_ids).exists()
