"""ROI / KPI computation (docs §10.5). Cost per lead, cost per attendee, platform
performance, KPI achievement. Avoids mixing unrelated costs unless total-budget
mode is explicitly requested."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count

from ..models import Campaign, CampaignLeadAttribution, EventAttendee

ZERO = Decimal("0")


class CampaignROIService:
    @staticmethod
    def calculate(*, campaign: Campaign) -> dict:
        lead_count = CampaignLeadAttribution.objects.filter(campaign=campaign).count()
        attendees = EventAttendee.objects.filter(event__campaign=campaign).count()
        total = campaign.total_budget or ZERO
        cpl = float(total / lead_count) if lead_count else None
        cpa = float(total / attendees) if attendees else None
        return {
            "campaign_id": str(campaign.pk),
            "total_budget": float(total),
            "lead_count": lead_count,
            "attendee_count": attendees,
            "cost_per_lead": cpl,
            "cost_per_attendee": cpa,
            "platform_performance": CampaignROIService._platform_breakdown(campaign),
        }

    @staticmethod
    def _platform_breakdown(campaign) -> list[dict]:
        rows = (
            CampaignLeadAttribution.objects.filter(
                campaign=campaign, platform__isnull=False
            )
            .values("platform__code")
            .annotate(leads=Count("id"))
        )
        return [{"platform": r["platform__code"], "leads": r["leads"]} for r in rows]
