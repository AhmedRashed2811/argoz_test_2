"""Bridge between the campaigns page (denormalized nested JS payload) and the
normalized marketing models (docs §10). Heavy nested child creation lives here,
never in views (§10.3). All budget writes still flow through CampaignBudgetService;
audit + notifications are emitted via CampaignCreationService."""
from __future__ import annotations

import base64
import uuid
from datetime import date
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.core.exceptions import ValidationError

from ..constants import ApprovalStatus, CampaignType
from ..models import (
    Campaign,
    CampaignAsset,
    EventCatering,
    EventCelebrity,
    EventGiveaway,
    EventRecord,
    ExhibitionRecord,
    OtherCost,
    Project,
    SocialMediaAdRecord,
    SocialMediaPlatformLine,
    SocialPlatformDefinition,
    StreetAdLocation,
    StreetAdRecord,
    StreetAdTypeDefinition,
    StreetAdTypeLine,
    TVAdRecord,
    TVChannel,
    TVSlot,
)
from .campaign_budget_service import CampaignBudgetService
from .campaign_creation_service import CampaignCreationService

# JS type tokens <-> stable model codes (docs §10.1).
_TYPE_TO_CODE = {
    "events": CampaignType.EVENTS, "tv": CampaignType.TV_ADS,
    "street": CampaignType.STREET_ADS, "social": CampaignType.SOCIAL_MEDIA,
    "exhibition": CampaignType.EXHIBITION,
}
_CODE_TO_TYPE = {v: k for k, v in _TYPE_TO_CODE.items()}
_TO_APPROVAL = {
    "pending": ApprovalStatus.PENDING, "approved": ApprovalStatus.APPROVED,
    "semi": ApprovalStatus.SEMI_APPROVED, "not-approved": ApprovalStatus.NOT_APPROVED,
}
_FROM_APPROVAL = {v: k for k, v in _TO_APPROVAL.items()}


def _d(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg",
        "image/gif": "gif", "image/webp": "webp", "image/svg+xml": "svg"}


def _save_assets(campaign, related_type, related_id, items, actor, existing_by_url, claimed):
    """New base64 data-URLs become CampaignAsset files on disk (not DB text).
    Items that are already URLs are re-pointed to the (rebuilt) child and kept;
    anything not seen here is later pruned, so removed images are deleted."""
    for item in items or []:
        data = item if isinstance(item, str) else item.get("data", "")
        if not data:
            continue
        if data.startswith("data:"):
            try:
                header, payload = data.split(",", 1)
                mime = header.split(";")[0].removeprefix("data:")
                content = base64.b64decode(payload)
            except Exception:
                continue
            ext = _EXT.get(mime, "bin")
            asset = CampaignAsset(
                campaign=campaign, related_type=related_type,
                related_id=related_id, asset_type="IMAGE", uploaded_by=actor,
            )
            asset.file.save(f"{related_type}_{uuid.uuid4().hex}.{ext}",
                            ContentFile(content), save=True)
            claimed.add(asset.id)
        else:  # existing image URL — keep it, re-point to the rebuilt child
            asset = existing_by_url.get(data)
            if asset:
                if asset.related_type != related_type or str(asset.related_id) != str(related_id):
                    asset.related_type = related_type
                    asset.related_id = related_id
                    asset.save(update_fields=["related_type", "related_id"])
                claimed.add(asset.id)


class CampaignPayloadService:
    # ── inbound: payload -> models ────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def create(*, company, actor, payload, request_meta=None) -> Campaign:
        name = (payload.get("name") or "").strip()
        if not name:
            raise ValidationError("Campaign name is required.")
        start, end = _date(payload.get("startDate")), _date(payload.get("endDate"))
        if not start or not end:
            raise ValidationError("Start and end dates are required.")
        codes = [_TYPE_TO_CODE[t] for t in payload.get("campaignTypes", []) if t in _TYPE_TO_CODE]

        campaign = CampaignCreationService.create_campaign(
            company=company, actor=actor, name=name,
            description=(payload.get("description") or "").strip(),
            start_date=start, end_date=end, selected_types=codes,
            request_meta=request_meta,
            **CampaignPayloadService._target_fields(company, payload),
        )
        CampaignPayloadService._rebuild_children(campaign, actor, payload)
        CampaignBudgetService.recalculate(campaign=campaign, actor=actor)
        return campaign

    @staticmethod
    @transaction.atomic
    def update(*, campaign: Campaign, actor, payload, request_meta=None) -> Campaign:
        codes = [_TYPE_TO_CODE[t] for t in payload.get("campaignTypes", []) if t in _TYPE_TO_CODE]
        CampaignCreationService.update_campaign(
            campaign=campaign, actor=actor, request_meta=request_meta,
            name=(payload.get("name") or campaign.name).strip(),
            description=(payload.get("description") or "").strip(),
            start_date=_date(payload.get("startDate")) or campaign.start_date,
            end_date=_date(payload.get("endDate")) or campaign.end_date,
            **CampaignPayloadService._target_fields(campaign.company, payload),
        )
        campaign.selected_types.all().delete()
        for code in codes:
            campaign.selected_types.create(type_code=code)
        # ponytail: full replace of child records on update — the form posts the
        # whole campaign. Switch to a diff if edit churn ever matters.
        CampaignPayloadService._rebuild_children(campaign, actor, payload)
        CampaignBudgetService.recalculate(campaign=campaign, actor=actor)
        return campaign

    @staticmethod
    @transaction.atomic
    def delete(*, campaign: Campaign, actor, request_meta=None) -> None:
        AuditService.log(
            action=AuditAction.DELETE, instance=campaign, actor=actor,
            company=campaign.company, module="marketing", request_meta=request_meta,
            before={"name": campaign.name},
        )
        campaign.delete()

    # ── target project (free-text name <-> Project FK) ────────────────────
    @staticmethod
    def _target_fields(company, payload):
        proj_name = (payload.get("interestedProject") or "").strip()
        if not proj_name:
            return {"target_type": "", "target_id": None}
        project, _ = Project.objects.get_or_create(company=company, name=proj_name)
        return {"target_type": "PROJECT", "target_id": project.id}

    # ── child records ─────────────────────────────────────────────────────
    @staticmethod
    def _rebuild_children(campaign, actor, payload):
        for related in ("events", "tv_ads", "street_ads", "exhibitions",
                        "social_ads", "other_costs"):
            getattr(campaign, related).all().delete()

        # Media is preserved across the child rebuild by matching on URL; assets
        # not re-claimed below are pruned (their files removed via post_delete).
        existing_by_url = {a.file.url: a for a in campaign.assets.all() if a.file}
        claimed = set()

        sel = set(payload.get("campaignTypes", []))

        def _section(key, token):
            return payload.get(key, []) if token in sel else []

        events_by_name = {}
        for ev in _section("eventsMulti", "events"):
            record = EventRecord.objects.create(
                campaign=campaign, name=(ev.get("name") or "").strip(),
                venue=(ev.get("place") or "").strip(), event_date=_date(ev.get("date")),
                budget=_d(ev.get("budget")), description=(ev.get("description") or "").strip(),
                target_attendees=int(ev.get("targetAttendees") or 0),
            )
            events_by_name[record.name] = record
            _save_assets(campaign, "event_logo", record.id, ev.get("logo"), actor, existing_by_url, claimed)
            _save_assets(campaign, "event_image", record.id, ev.get("images"), actor, existing_by_url, claimed)
            for cel in ev.get("celebrities", []):
                if cel.get("name"):
                    EventCelebrity.objects.create(event=record, name=cel["name"], budget=_d(cel.get("budget")))
            for gv in ev.get("giveaways", []):
                if gv.get("name"):
                    EventGiveaway.objects.create(event=record, name=gv["name"], budget=_d(gv.get("budget")))
            for ct in ev.get("catering", []):
                if ct.get("name"):
                    EventCatering.objects.create(event=record, name=ct["name"], budget=_d(ct.get("budget")))

        for tv in _section("tvMulti", "tv"):
            record = TVAdRecord.objects.create(
                campaign=campaign, name=(tv.get("name") or "").strip(),
                start_date=_date(tv.get("start")), end_date=_date(tv.get("end")),
                budget=_d(tv.get("budget")), description=(tv.get("description") or "").strip(),
            )
            for ch in tv.get("channels", []):
                channel = TVChannel.objects.create(
                    tv_ad=record, channel_name=(ch.get("channelName") or "").strip(),
                    budget=_d(ch.get("budget")),
                )
                _save_assets(campaign, "tv_channel_media", channel.id, ch.get("media"), actor, existing_by_url, claimed)
                for sl in ch.get("slots", []):
                    TVSlot.objects.create(
                        tv_ad=record, number_of_appearances=int(sl.get("count") or 0),
                        notes=(sl.get("time") or "").strip(),
                    )

        for st in _section("streetMulti", "street"):
            record = StreetAdRecord.objects.create(
                campaign=campaign, name=(st.get("name") or "").strip(),
                start_date=_date(st.get("start")), end_date=_date(st.get("end")),
                budget=_d(st.get("budget")), description=(st.get("description") or "").strip(),
            )
            for at in st.get("adTypes", []):
                definition, _ = StreetAdTypeDefinition.objects.get_or_create(
                    code=at["type"][:40], defaults={"name": at["type"]},
                )
                line = StreetAdTypeLine.objects.create(
                    street_ad=record, ad_type=definition,
                    total_number=int(at.get("count") or 0), budget=_d(at.get("budget")),
                )
                for loc in at.get("locations", []):
                    if loc.get("name"):
                        StreetAdLocation.objects.create(
                            type_line=line, location_text=loc["name"], budget=_d(loc.get("budget")),
                        )
            _save_assets(campaign, "street_image", record.id, st.get("images"), actor, existing_by_url, claimed)

        for ex in _section("exhibitionMulti", "exhibition"):
            ExhibitionRecord.objects.create(
                campaign=campaign, name=(ex.get("name") or "").strip(),
                place=(ex.get("place") or "").strip(),
                start_date=_date(ex.get("start")), end_date=_date(ex.get("end")),
                budget=_d(ex.get("budget")),
            )

        for sm in _section("socialMulti", "social"):
            record = SocialMediaAdRecord.objects.create(
                campaign=campaign, name=(sm.get("adName") or "").strip(),
                start_date=_date(sm.get("start")), end_date=_date(sm.get("end")),
                target_kpi=(sm.get("targetKpi") or "").strip(),
                linked_event=events_by_name.get((sm.get("linkedEventId") or "").strip()),
            )
            _save_assets(campaign, "social_image", record.id, sm.get("images"), actor, existing_by_url, claimed)
            for pb in sm.get("platformBudgets", []):
                platform, _ = SocialPlatformDefinition.objects.get_or_create(
                    code=pb["platform"][:40], defaults={"name": pb["platform"]},
                )
                SocialMediaPlatformLine.objects.create(
                    social_ad=record, platform=platform, budget=_d(pb.get("budget")),
                )

        for oc in payload.get("otherCosts", []):
            if oc.get("value") or oc.get("reason"):
                OtherCost.objects.create(
                    campaign=campaign, value=_d(oc.get("value")),
                    reason=(oc.get("reason") or "").strip(), created_by=actor,
                )

        campaign.assets.exclude(id__in=claimed).delete()

    # ── outbound: models -> payload ───────────────────────────────────────
    @staticmethod
    def _assets_map(campaign):
        amap = {}
        for a in campaign.assets.all():
            if a.file:
                amap.setdefault((a.related_type, str(a.related_id)), []).append(a.file.url)
        return amap

    @staticmethod
    def serialize(campaign: Campaign) -> dict:
        types = [_CODE_TO_TYPE[t.type_code] for t in campaign.selected_types.all()
                 if t.type_code in _CODE_TO_TYPE]
        assets = CampaignPayloadService._assets_map(campaign)
        return {
            "id": str(campaign.id),
            "name": campaign.name,
            "description": campaign.description,
            "startDate": campaign.start_date.isoformat() if campaign.start_date else "",
            "endDate": campaign.end_date.isoformat() if campaign.end_date else "",
            "campaignTypes": types,
            "approval": _FROM_APPROVAL.get(campaign.approval_status, "pending"),
            "approvalReason": campaign.approval_reason,
            "interestedProject": CampaignPayloadService._project_name(campaign),
            # Leads are attribution-derived (docs §10.5); the per-type editor is a
            # display aid and is not persisted.
            "leads": getattr(campaign, "lead_count", 0) or 0,
            "typeLeads": {},
            "otherCosts": [{"value": float(oc.value), "reason": oc.reason}
                           for oc in campaign.other_costs.all()],
            "eventsMulti": [CampaignPayloadService._event(e, assets) for e in campaign.events.all()],
            "tvMulti": [CampaignPayloadService._tv(t, assets) for t in campaign.tv_ads.all()],
            "streetMulti": [CampaignPayloadService._street(s, assets) for s in campaign.street_ads.all()],
            "socialMulti": [CampaignPayloadService._social(s, assets) for s in campaign.social_ads.all()],
            "exhibitionMulti": [CampaignPayloadService._exhibition(x)
                                for x in campaign.exhibitions.all()],
        }

    @staticmethod
    def _project_name(campaign):
        if campaign.target_type == "PROJECT" and campaign.target_id:
            project = Project.objects.filter(id=campaign.target_id).first()
            return project.name if project else ""
        return ""

    @staticmethod
    def _event(e, assets):
        return {
            "name": e.name, "place": e.venue,
            "date": e.event_date.isoformat() if e.event_date else "",
            "budget": float(e.budget), "targetAttendees": e.target_attendees,
            "description": e.description,
            "logo": assets.get(("event_logo", str(e.id)), []),
            "images": assets.get(("event_image", str(e.id)), []),
            "celebrities": [{"name": c.name, "budget": float(c.budget)} for c in e.celebrities.all()],
            "giveaways": [{"name": g.name, "budget": float(g.budget)} for g in e.giveaways.all()],
            "catering": [{"name": c.name, "budget": float(c.budget)} for c in e.catering.all()],
        }

    @staticmethod
    def _tv(t, assets):
        channels = [{"channelName": c.channel_name, "budget": float(c.budget),
                     "media": assets.get(("tv_channel_media", str(c.id)), []),
                     "slots": [{"count": s.number_of_appearances, "time": s.notes}
                               for s in t.slots.all()]}
                    for c in t.channels.all()]
        return {
            "name": t.name, "description": t.description,
            "start": t.start_date.isoformat() if t.start_date else "",
            "end": t.end_date.isoformat() if t.end_date else "",
            "budget": float(t.budget), "channels": channels,
            "channel": ", ".join(c["channelName"] for c in channels if c["channelName"]),
        }

    @staticmethod
    def _street(s, assets):
        return {
            "name": s.name, "description": s.description,
            "start": s.start_date.isoformat() if s.start_date else "",
            "end": s.end_date.isoformat() if s.end_date else "",
            "budget": float(s.budget),
            "images": assets.get(("street_image", str(s.id)), []),
            "adTypes": [{"type": line.ad_type.name, "count": line.total_number,
                         "budget": float(line.budget),
                         "locations": [{"name": loc.location_text, "budget": float(loc.budget)}
                                       for loc in line.locations.all()]}
                        for line in s.type_lines.all()],
        }

    @staticmethod
    def _social(s, assets):
        platform_budgets = [{"platform": p.platform.name, "budget": float(p.budget)}
                            for p in s.platform_lines.all()]
        return {
            "adName": s.name, "targetKpi": s.target_kpi,
            "platforms": [pb["platform"] for pb in platform_budgets],
            "platformBudgets": platform_budgets,
            "budget": sum(pb["budget"] for pb in platform_budgets),
            "start": s.start_date.isoformat() if s.start_date else "",
            "end": s.end_date.isoformat() if s.end_date else "",
            "linkedEventId": s.linked_event.name if s.linked_event else "",
            "images": assets.get(("social_image", str(s.id)), []),
        }

    @staticmethod
    def _exhibition(x):
        return {
            "name": x.name, "place": x.place,
            "start": x.start_date.isoformat() if x.start_date else "",
            "end": x.end_date.isoformat() if x.end_date else "",
            "budget": float(x.budget),
        }
