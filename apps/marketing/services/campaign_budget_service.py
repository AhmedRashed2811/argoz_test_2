"""Budget aggregation (docs §10.2, §10.4). Total = selected type main budgets +
repeatable sub-sections + channel/platform/location budgets + Other Costs.
All budget writes flow through here; stores a snapshot for traceability."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Sum

from ..models import (
    Campaign,
    CampaignBudgetSnapshot,
    EventCatering,
    EventCelebrity,
    EventGiveaway,
    EventPrintOut,
    EventRecord,
    ExhibitionCatering,
    ExhibitionCelebrity,
    ExhibitionGiveaway,
    ExhibitionPrintOut,
    ExhibitionRecord,
    OtherCost,
    SocialMediaAdRecord,
    SocialMediaPlatformLine,
    StreetAdLocation,
    StreetAdRecord,
    StreetAdTypeLine,
    TVAdRecord,
    TVChannel,
)

ZERO = Decimal("0")


def _sum_field(items, field="budget") -> Decimal:
    return sum((getattr(item, field) or ZERO for item in items), ZERO)


class CampaignBudgetService:
    @staticmethod
    @transaction.atomic
    def add_other_cost(*, campaign: Campaign, value, reason, actor=None) -> Decimal:
        """Record an ad-hoc Other Cost and return the recalculated total."""
        OtherCost.objects.create(
            campaign=campaign, value=value, reason=reason, created_by=actor,
        )
        return CampaignBudgetService.recalculate(campaign=campaign, actor=actor)

    @staticmethod
    @transaction.atomic
    def recalculate(*, campaign: Campaign, actor=None) -> Decimal:
        breakdown = {}
        total = ZERO

        # Events: main + celebrities + giveaways + catering (docs §10.2).
        # prefetch_related fetches all sub-rows in 3 queries instead of 3×N.
        events_qs = EventRecord.objects.filter(campaign=campaign).prefetch_related(
            Prefetch("celebrities", queryset=EventCelebrity.objects.only("budget")),
            Prefetch("giveaways", queryset=EventGiveaway.objects.only("budget")),
            Prefetch("catering", queryset=EventCatering.objects.only("budget")),
            Prefetch("printouts", queryset=EventPrintOut.objects.only("budget")),
        )
        events = ZERO
        for event in events_qs:
            events += event.budget or ZERO
            events += _sum_field(event.celebrities.all())
            events += _sum_field(event.giveaways.all())
            events += _sum_field(event.catering.all())
            events += _sum_field(event.printouts.all())
        breakdown["events"] = float(events)
        total += events

        # TV: main + channels (+ slots only if policy defines slot costing).
        tv_qs = TVAdRecord.objects.filter(campaign=campaign).prefetch_related(
            Prefetch("channels", queryset=TVChannel.objects.only("budget")),
        )
        tv = ZERO
        for tv_ad in tv_qs:
            tv += tv_ad.budget or ZERO
            tv += _sum_field(tv_ad.channels.all())
        breakdown["tv_ads"] = float(tv)
        total += tv

        # Street: main + type lines + locations.
        street_qs = StreetAdRecord.objects.filter(campaign=campaign).prefetch_related(
            Prefetch(
                "type_lines",
                queryset=StreetAdTypeLine.objects.only("budget").prefetch_related(
                    Prefetch(
                        "locations",
                        queryset=StreetAdLocation.objects.only("budget"),
                    )
                ),
            )
        )
        street = ZERO
        for ad in street_qs:
            street += ad.budget or ZERO
            for line in ad.type_lines.all():
                street += line.budget or ZERO
                street += _sum_field(line.locations.all())
        breakdown["street_ads"] = float(street)
        total += street

        # Exhibition: main + celebrities + giveaways + catering + printouts (task 3).
        exhibition_qs = ExhibitionRecord.objects.filter(campaign=campaign).prefetch_related(
            Prefetch("celebrities", queryset=ExhibitionCelebrity.objects.only("budget")),
            Prefetch("giveaways", queryset=ExhibitionGiveaway.objects.only("budget")),
            Prefetch("catering", queryset=ExhibitionCatering.objects.only("budget")),
            Prefetch("printouts", queryset=ExhibitionPrintOut.objects.only("budget")),
        )
        exhibition = ZERO
        for ex in exhibition_qs:
            exhibition += ex.budget or ZERO
            exhibition += _sum_field(ex.celebrities.all())
            exhibition += _sum_field(ex.giveaways.all())
            exhibition += _sum_field(ex.catering.all())
            exhibition += _sum_field(ex.printouts.all())
        breakdown["exhibition"] = float(exhibition)
        total += exhibition

        social_qs = SocialMediaAdRecord.objects.filter(
            campaign=campaign
        ).prefetch_related(
            Prefetch(
                "platform_lines",
                queryset=SocialMediaPlatformLine.objects.only("budget"),
            )
        )
        social = ZERO
        for ad in social_qs:
            social += _sum_field(ad.platform_lines.all())
        breakdown["social_media"] = float(social)
        total += social

        other = (
            OtherCost.objects.filter(campaign=campaign)
            .aggregate(s=Sum("value"))
            .get("s") or ZERO
        )
        breakdown["other_costs"] = float(other)
        total += other

        campaign.total_budget = total
        campaign.save(update_fields=["total_budget", "updated_at"])
        CampaignBudgetSnapshot.objects.create(
            campaign=campaign, total_budget=total, breakdown_json=breakdown,
            calculated_by=actor,
        )
        return total
