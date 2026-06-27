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


def _kpi_number(value) -> Decimal:
    """Extract the numeric target from a free-text KPI label (e.g. '1,000 leads'
    -> 1000). Returns 0 when no number is present."""
    import re

    digits = re.sub(r"[^\d.]", "", str(value or "").replace(",", ""))
    try:
        return Decimal(digits) if digits else Decimal("0")
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
        from .campaign_approval_service import CampaignApprovalService

        restrict_editing = CampaignApprovalService.restrict_editing(campaign.company)
        if restrict_editing:
            if campaign.approval_status == ApprovalStatus.APPROVED:
                raise ValidationError("Approved campaigns cannot be edited under current company policy.")
            elif campaign.approval_status == ApprovalStatus.SEMI_APPROVED:
                db_state = CampaignPayloadService.serialize(campaign)
                rejected = campaign.rejected_budgets or []
                
                # Check general fields
                if (payload.get("name") or "").strip() != (db_state.get("name") or "").strip():
                    raise ValidationError("Cannot edit name of a semi-approved campaign.")
                if (payload.get("description") or "").strip() != (db_state.get("description") or "").strip():
                    raise ValidationError("Cannot edit description of a semi-approved campaign.")
                if payload.get("startDate") != db_state.get("startDate"):
                    raise ValidationError("Cannot edit start date of a semi-approved campaign.")
                if payload.get("endDate") != db_state.get("endDate"):
                    raise ValidationError("Cannot edit end date of a semi-approved campaign.")
                if (payload.get("interestedProject") or "").strip() != (db_state.get("interestedProject") or "").strip():
                    raise ValidationError("Cannot edit target project of a semi-approved campaign.")
                
                # Check campaign types selection list
                payload_types = set(payload.get("campaignTypes") or [])
                db_types = set(db_state.get("campaignTypes") or [])
                if payload_types != db_types:
                    raise ValidationError("Cannot change campaign types of a semi-approved campaign.")
                
                # Helpers for validation
                def _str_eq(a, b):
                    return (a or "").strip() == (b or "").strip()
                
                def _num_eq(a, b):
                    try:
                        return abs(float(a or 0) - float(b or 0)) < 1e-4
                    except (ValueError, TypeError):
                        return False

                def _validate_sub_list(db_list, payload_list, fields_to_compare, rejected_keys, key_prefix, error_msg_template):
                    matched_indices = set()
                    for item_idx, db_item in enumerate(db_list):
                        item_key = key_prefix.format(item_idx=item_idx)
                        if item_key not in rejected_keys:
                            found = False
                            for p_idx, p_item in enumerate(payload_list):
                                if p_idx in matched_indices:
                                    continue
                                match = True
                                for f in fields_to_compare:
                                    val_a, val_b = db_item.get(f), p_item.get(f)
                                    if f in ("budget", "value", "amount"):
                                        if not _num_eq(val_a, val_b):
                                            match = False
                                            break
                                    else:
                                        if not _str_eq(val_a, val_b):
                                            match = False
                                            break
                                if match:
                                    matched_indices.add(p_idx)
                                    found = True
                                    break
                            if not found:
                                raise ValidationError(error_msg_template.format(name=db_item.get(fields_to_compare[0], "")))

                def _channel_eq(db_ch, p_ch):
                    if not _str_eq(db_ch.get("channelName"), p_ch.get("channelName")):
                        return False
                    if not _num_eq(db_ch.get("budget"), p_ch.get("budget")):
                        return False
                    db_slots = db_ch.get("slots") or []
                    p_slots = p_ch.get("slots") or []
                    if len(db_slots) != len(p_slots):
                        return False
                    for ds, ps in zip(db_slots, p_slots):
                        if int(ds.get("count") or 0) != int(ps.get("count") or 0):
                            return False
                        if not _str_eq(ds.get("time"), ps.get("time")):
                            return False
                    return True

                # Check approved sections
                # --- Granular Events validation ---
                p_events = payload.get("eventsMulti") or []
                d_events = db_state.get("eventsMulti") or []
                matched_event_indices = set()
                for ev_idx, db_ev in enumerate(d_events):
                    event_key = f"events.{ev_idx}.main"
                    if event_key not in rejected:
                        found = False
                        for p_idx, p_ev in enumerate(p_events):
                            if p_idx in matched_event_indices:
                                continue
                            if _str_eq(db_ev.get("name"), p_ev.get("name")) and \
                               _str_eq(db_ev.get("place"), p_ev.get("place")) and \
                               _str_eq(db_ev.get("date"), p_ev.get("date")) and \
                               _num_eq(db_ev.get("budget"), p_ev.get("budget")) and \
                               _num_eq(db_ev.get("targetAttendees"), p_ev.get("targetAttendees")) and \
                               _str_eq(db_ev.get("description"), p_ev.get("description")):
                                
                                matched_event_indices.add(p_idx)
                                found = True
                                
                                # Validate sub-lists of this event
                                _validate_sub_list(
                                    db_ev.get("celebrities") or [], p_ev.get("celebrities") or [],
                                    ["name", "budget"], rejected, f"events.{ev_idx}.celebrities.{{item_idx}}",
                                    "Approved celebrity '{name}' was modified or deleted."
                                )
                                _validate_sub_list(
                                    db_ev.get("giveaways") or [], p_ev.get("giveaways") or [],
                                    ["name", "budget"], rejected, f"events.{ev_idx}.giveaways.{{item_idx}}",
                                    "Approved giveaway '{name}' was modified or deleted."
                                )
                                _validate_sub_list(
                                    db_ev.get("catering") or [], p_ev.get("catering") or [],
                                    ["name", "budget"], rejected, f"events.{ev_idx}.catering.{{item_idx}}",
                                    "Approved catering item '{name}' was modified or deleted."
                                )
                                break
                        if not found:
                            raise ValidationError(f"Approved Event '{db_ev.get('name')}' main details were modified or deleted.")

                # --- Granular TV Ads validation ---
                p_tvs = payload.get("tvMulti") or []
                d_tvs = db_state.get("tvMulti") or []
                matched_tv_indices = set()
                for tv_idx, db_tv in enumerate(d_tvs):
                    tv_key = f"tv_ads.{tv_idx}.main"
                    if tv_key not in rejected:
                        found = False
                        for p_idx, p_tv in enumerate(p_tvs):
                            if p_idx in matched_tv_indices:
                                continue
                            if _str_eq(db_tv.get("name"), p_tv.get("name")) and \
                               _str_eq(db_tv.get("description"), p_tv.get("description")) and \
                               _str_eq(db_tv.get("start"), p_tv.get("start")) and \
                               _str_eq(db_tv.get("end"), p_tv.get("end")) and \
                               _num_eq(db_tv.get("budget"), p_tv.get("budget")):
                                
                                matched_tv_indices.add(p_idx)
                                found = True
                                
                                # Validate channels
                                db_channels = db_tv.get("channels") or []
                                p_channels = p_tv.get("channels") or []
                                matched_ch_indices = set()
                                for ch_idx, db_ch in enumerate(db_channels):
                                    ch_key = f"tv_ads.{tv_idx}.channels.{ch_idx}"
                                    if ch_key not in rejected:
                                        found_ch = False
                                        for p_c_idx, p_ch in enumerate(p_channels):
                                            if p_c_idx in matched_ch_indices:
                                                continue
                                            if _channel_eq(db_ch, p_ch):
                                                matched_ch_indices.add(p_c_idx)
                                                found_ch = True
                                                break
                                        if not found_ch:
                                            raise ValidationError(f"Approved Channel '{db_ch.get('channelName')}' in TV Ad '{db_tv.get('name')}' was modified or deleted.")
                                break
                        if not found:
                            raise ValidationError(f"Approved TV Ad '{db_tv.get('name')}' was modified or deleted.")

                # --- Granular Street Ads validation ---
                p_sts = payload.get("streetMulti") or []
                d_sts = db_state.get("streetMulti") or []
                matched_st_indices = set()
                for st_idx, db_st in enumerate(d_sts):
                    st_key = f"street_ads.{st_idx}.main"
                    if st_key not in rejected:
                        found = False
                        for p_idx, p_st in enumerate(p_sts):
                            if p_idx in matched_st_indices:
                                continue
                            if _str_eq(db_st.get("name"), p_st.get("name")) and \
                               _str_eq(db_st.get("description"), p_st.get("description")) and \
                               _str_eq(db_st.get("start"), p_st.get("start")) and \
                               _str_eq(db_st.get("end"), p_st.get("end")) and \
                               _num_eq(db_st.get("budget"), p_st.get("budget")):
                                
                                matched_st_indices.add(p_idx)
                                found = True
                                
                                # Validate adTypes
                                db_at = db_st.get("adTypes") or []
                                p_at = p_st.get("adTypes") or []
                                matched_at_indices = set()
                                for line_idx, db_line in enumerate(db_at):
                                    line_key = f"street_ads.{st_idx}.type_lines.{line_idx}"
                                    if line_key not in rejected:
                                        found_at = False
                                        for p_a_idx, p_line in enumerate(p_at):
                                            if p_a_idx in matched_at_indices:
                                                continue
                                            if _str_eq(db_line.get("type"), p_line.get("type")) and \
                                               _num_eq(db_line.get("count"), p_line.get("count")) and \
                                               _num_eq(db_line.get("budget"), p_line.get("budget")):
                                                
                                                # Validate locations
                                                db_locs = db_line.get("locations") or []
                                                p_locs = p_line.get("locations") or []
                                                matched_loc_indices = set()
                                                for loc_idx, db_loc in enumerate(db_locs):
                                                    loc_key = f"street_ads.{st_idx}.type_lines.{line_idx}.locations.{loc_idx}"
                                                    if loc_key not in rejected:
                                                        found_loc = False
                                                        for p_l_idx, p_loc in enumerate(p_locs):
                                                            if p_l_idx in matched_loc_indices:
                                                                continue
                                                            if _str_eq(db_loc.get("name"), p_loc.get("name")) and \
                                                               _num_eq(db_loc.get("budget"), p_loc.get("budget")):
                                                                matched_loc_indices.add(p_l_idx)
                                                                found_loc = True
                                                                break
                                                        if not found_loc:
                                                            raise ValidationError(f"Approved Location '{db_loc.get('name')}' in Street Ad '{db_st.get('name')}' was modified or deleted.")
                                                
                                                matched_at_indices.add(p_a_idx)
                                                found_at = True
                                                break
                                        if not found_at:
                                            raise ValidationError(f"Approved Ad Type '{db_line.get('type')}' in Street Ad '{db_st.get('name')}' was modified or deleted.")
                                break
                        if not found:
                            raise ValidationError(f"Approved Street Ad '{db_st.get('name')}' was modified or deleted.")

                # --- Granular Social Ads validation ---
                p_sos = payload.get("socialMulti") or []
                d_sos = db_state.get("socialMulti") or []
                matched_soc_indices = set()
                for sm_idx, db_sm in enumerate(d_sos):
                    sm_key = f"social_ads.{sm_idx}.main"
                    if sm_key not in rejected:
                        found = False
                        for p_idx, p_sm in enumerate(p_sos):
                            if p_idx in matched_soc_indices:
                                continue
                            if _str_eq(db_sm.get("adName"), p_sm.get("adName")) and \
                               _str_eq(db_sm.get("targetKpi"), p_sm.get("targetKpi")) and \
                               _str_eq(db_sm.get("start"), p_sm.get("start")) and \
                               _str_eq(db_sm.get("end"), p_sm.get("end")) and \
                               _str_eq(db_sm.get("linkedEventId"), p_sm.get("linkedEventId")):
                                
                                matched_soc_indices.add(p_idx)
                                found = True
                                
                                # Validate platform budgets
                                db_pb = db_sm.get("platformBudgets") or []
                                p_pb = p_sm.get("platformBudgets") or []
                                matched_pb_indices = set()
                                for p_idx_inner, db_p in enumerate(db_pb):
                                    pb_key = f"social_ads.{sm_idx}.platform_lines.{p_idx_inner}"
                                    if pb_key not in rejected:
                                        found_pb = False
                                        for p_pb_idx, p_p in enumerate(p_pb):
                                            if p_pb_idx in matched_pb_indices:
                                                continue
                                            if _str_eq(db_p.get("platform"), p_p.get("platform")) and \
                                               _num_eq(db_p.get("budget"), p_p.get("budget")):
                                                matched_pb_indices.add(p_pb_idx)
                                                found_pb = True
                                                break
                                        if not found_pb:
                                            raise ValidationError(f"Approved Platform '{db_p.get('platform')}' budget in Social Ad '{db_sm.get('adName')}' was modified or deleted.")
                                break
                        if not found:
                            raise ValidationError(f"Approved Social Ad '{db_sm.get('adName')}' was modified or deleted.")

                # --- Granular Exhibition validation ---
                p_exs = payload.get("exhibitionMulti") or []
                d_exs = db_state.get("exhibitionMulti") or []
                matched_ex_indices = set()
                for ex_idx, db_ex in enumerate(d_exs):
                    ex_key = f"exhibitions.{ex_idx}.main"
                    if ex_key not in rejected:
                        found = False
                        for p_idx, p_ex in enumerate(p_exs):
                            if p_idx in matched_ex_indices:
                                continue
                            if _str_eq(db_ex.get("name"), p_ex.get("name")) and \
                               _str_eq(db_ex.get("place"), p_ex.get("place")) and \
                               _str_eq(db_ex.get("start"), p_ex.get("start")) and \
                               _str_eq(db_ex.get("end"), p_ex.get("end")) and \
                               _num_eq(db_ex.get("budget"), p_ex.get("budget")):
                                matched_ex_indices.add(p_idx)
                                found = True
                                break
                        if not found:
                            raise ValidationError(f"Approved Exhibition '{db_ex.get('name')}' was modified or deleted.")

                # --- Granular Other Costs validation ---
                p_oc = payload.get("otherCosts") or []
                d_oc = db_state.get("otherCosts") or []
                matched_oc_indices = set()
                for oc_idx, db_o in enumerate(d_oc):
                    oc_key = f"other_costs.{oc_idx}"
                    if oc_key not in rejected:
                        found = False
                        for p_idx, p_o in enumerate(p_oc):
                            if p_idx in matched_oc_indices:
                                continue
                            if _num_eq(db_o.get("value"), p_o.get("value")) and \
                               _str_eq(db_o.get("reason"), p_o.get("reason")):
                                matched_oc_indices.add(p_idx)
                                found = True
                                break
                        if not found:
                            raise ValidationError(f"Approved Other Cost '{db_o.get('reason')}' was modified or deleted.")

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
            # The form captures one ad-level target (free text). Spread it evenly
            # across the ad's platform lines so the per-platform report column
            # (Sum of target_kpi_value) reconstructs the ad total.
            platform_budgets = sm.get("platformBudgets", [])
            target_total = _kpi_number(sm.get("targetKpi"))
            per_platform = (
                target_total / len(platform_budgets) if platform_budgets else Decimal("0")
            )
            for pb in platform_budgets:
                platform, _ = SocialPlatformDefinition.objects.get_or_create(
                    code=pb["platform"][:40], defaults={"name": pb["platform"]},
                )
                SocialMediaPlatformLine.objects.create(
                    social_ad=record, platform=platform, budget=_d(pb.get("budget")),
                    target_kpi_value=per_platform,
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
        type_leads = {
            "events": sum(e.lead_count for e in campaign.events.all()),
            "tv": sum(t.lead_count for t in campaign.tv_ads.all()),
            "street": sum(s.lead_count for s in campaign.street_ads.all()),
            "social": sum(s.lead_count for s in campaign.social_ads.all()),
            "exhibition": sum(x.lead_count for x in campaign.exhibitions.all()),
        }
        return {
            "id": str(campaign.id),
            "name": campaign.name,
            "description": campaign.description,
            "startDate": campaign.start_date.isoformat() if campaign.start_date else "",
            "endDate": campaign.end_date.isoformat() if campaign.end_date else "",
            "campaignTypes": types,
            "approval": _FROM_APPROVAL.get(campaign.approval_status, "pending"),
            "approvalReason": campaign.approval_reason,
            "rejected_budgets": campaign.rejected_budgets or [],
            "interestedProject": CampaignPayloadService._project_name(campaign),
            # Leads are attribution-derived (docs §10.5); the per-type editor is a
            # display aid and is not persisted.
            "leads": getattr(campaign, "lead_count", 0) or 0,
            "typeLeads": type_leads,
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
            "leads": int(e.lead_count),
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
            "leads": int(t.lead_count),
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
            "leads": int(s.lead_count),
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
            "leads": int(s.lead_count),
        }

    @staticmethod
    def _exhibition(x):
        return {
            "name": x.name, "place": x.place,
            "start": x.start_date.isoformat() if x.start_date else "",
            "end": x.end_date.isoformat() if x.end_date else "",
            "budget": float(x.budget),
            "leads": int(x.lead_count),
        }
