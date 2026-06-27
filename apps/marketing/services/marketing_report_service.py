"""Financial & marketing report aggregation (docs §10.5). Read-only: rolls up
campaign budgets, lead counts, social-platform KPIs and event funnels for the
report page. All figures are company-scoped; the view/API stay thin and call
``build`` here."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.leads.constants import StageCode
from apps.leads.models import Lead

from ..constants import CampaignType, ChannelType
from ..models import (
    CampaignLeadAttribution,
    EventRecord,
    ExhibitionRecord,
    SocialMediaPlatformLine,
    SocialPlatformDefinition,
    StreetAdRecord,
    TVAdRecord,
)

ZERO = Decimal("0")

# CampaignType -> (display label, Lead.campaign_child_type code).
_TYPE_META = [
    (CampaignType.SOCIAL_MEDIA, "Social Media", ChannelType.SOCIAL_MEDIA_AD),
    (CampaignType.EVENTS, "Events & Launch", ChannelType.EVENT),
    (CampaignType.EXHIBITION, "Exhibitions", ChannelType.EXHIBITION),
    (CampaignType.STREET_ADS, "Street Ads", ChannelType.STREET_AD),
    (CampaignType.TV_ADS, "TV Ads", ChannelType.TV_AD),
]


def _num(value) -> float:
    return float(value or ZERO)


def _kpi_number(value) -> Decimal:
    """Extract the numeric target from a free-text KPI label (e.g. '1,000 leads'
    -> 1000). Returns 0 when no number is present."""
    import re

    digits = re.sub(r"[^\d.]", "", str(value or "").replace(",", ""))
    try:
        return Decimal(digits) if digits else ZERO
    except Exception:
        return ZERO


class MarketingReportService:
    @staticmethod
    def build(company) -> dict:
        return {
            "campaignTypes": MarketingReportService._campaign_types(company),
            "socialKpis": MarketingReportService._social_kpis(company),
            "events": MarketingReportService._events(company),
        }

    @staticmethod
    def _type_budgets(company) -> dict:
        """Sum of channel-record budgets per CampaignType, company-wide."""
        social = SocialMediaPlatformLine.objects.filter(
            social_ad__campaign__company=company
        ).aggregate(s=Sum("budget"))["s"]
        return {
            CampaignType.SOCIAL_MEDIA: social,
            CampaignType.EVENTS: EventRecord.objects.filter(
                campaign__company=company
            ).aggregate(s=Sum("budget"))["s"],
            CampaignType.EXHIBITION: ExhibitionRecord.objects.filter(
                campaign__company=company
            ).aggregate(s=Sum("budget"))["s"],
            CampaignType.STREET_ADS: StreetAdRecord.objects.filter(
                campaign__company=company
            ).aggregate(s=Sum("budget"))["s"],
            CampaignType.TV_ADS: TVAdRecord.objects.filter(
                campaign__company=company
            ).aggregate(s=Sum("budget"))["s"],
        }

    @staticmethod
    def _campaign_types(company) -> list[dict]:
        budgets = MarketingReportService._type_budgets(company)
        # Leads + interested counts grouped by channel type in one pass.
        rows = {
            r["campaign_child_type"]: r
            for r in Lead.objects.filter(company=company)
            .exclude(campaign_child_type="")
            .values("campaign_child_type")
            .annotate(
                total=Count("id"),
                interested=Count(
                    "id", filter=Q(current_stage__code=StageCode.INTERESTED)
                ),
            )
        }
        out = []
        for type_code, label, channel in _TYPE_META:
            r = rows.get(channel, {})
            out.append({
                "type_code": type_code,
                "label": label,
                "budget": _num(budgets.get(type_code)),
                "leads_count": r.get("total", 0),
                "interested_leads": r.get("interested", 0),
            })
        return out

    @staticmethod
    def _social_kpis(company) -> list[dict]:
        # Budget per platform + target sourced from the ad record's KPI (free
        # text on SocialMediaAdRecord.target_kpi, parsed to a number). Each ad's
        # target is split evenly across its platform lines so the per-platform
        # sum reconstructs the ad total.
        lines = list(
            SocialMediaPlatformLine.objects.filter(
                social_ad__campaign__company=company
            ).select_related("social_ad")
        )
        ad_line_count: dict = {}
        for line in lines:
            ad_line_count[line.social_ad_id] = ad_line_count.get(line.social_ad_id, 0) + 1
        budget_by_platform: dict = {}
        target_by_platform: dict = {}
        for line in lines:
            budget_by_platform[line.platform_id] = (
                budget_by_platform.get(line.platform_id, ZERO) + (line.budget or ZERO)
            )
            ad_target = _kpi_number(line.social_ad.target_kpi)
            per_line = ad_target / ad_line_count[line.social_ad_id]
            target_by_platform[line.platform_id] = (
                target_by_platform.get(line.platform_id, ZERO) + per_line
            )
        # Actual leads attributed per platform.
        actual_rows = {
            r["platform_id"]: r["actual"]
            for r in CampaignLeadAttribution.objects.filter(
                campaign__company=company, platform__isnull=False
            )
            .values("platform_id")
            .annotate(actual=Count("id"))
        }
        platforms = SocialPlatformDefinition.objects.filter(
            id__in=budget_by_platform.keys()
        ).order_by("name")
        out = []
        for p in platforms:
            target = _num(target_by_platform.get(p.id))
            actual = actual_rows.get(p.id, 0)
            out.append({
                "platform": p.name,
                "target": target,
                "actual": actual,
                "budget": _num(budget_by_platform.get(p.id)),
                "status": "EXCEEDED" if target and actual >= target
                else "UNDERPERFORMING",
            })
        return out

    @staticmethod
    def _events(company) -> list[dict]:
        # Leads generated by each event are recorded as CampaignLeadAttribution
        # rows (event FK), not EventAttendee check-ins — so the funnel counts
        # attributed leads: "Checked In" = leads from the event, "Interested" =
        # those now in the Interested stage.
        total: dict = {}
        interested: dict = {}
        attributions = CampaignLeadAttribution.objects.filter(
            campaign__company=company, event__isnull=False
        ).select_related("lead__current_stage")
        for a in attributions:
            total[a.event_id] = total.get(a.event_id, 0) + 1
            stage = a.lead.current_stage if a.lead_id else None
            if stage and stage.code == StageCode.INTERESTED:
                interested[a.event_id] = interested.get(a.event_id, 0) + 1
        out = []
        for e in EventRecord.objects.filter(campaign__company=company).order_by("name"):
            target = e.target_attendees or 0
            checked_in = total.get(e.id, 0)
            converted = interested.get(e.id, 0)
            out.append({
                "name": e.name,
                "target": target,
                "checked_in": checked_in,
                "converted": converted,
                "rate": round(converted / target * 100, 1) if target else 0,
            })
        return out
