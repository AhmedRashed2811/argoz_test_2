from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.companies.models import Company
from apps.core.exceptions import ValidationError
from apps.marketing.constants import ApprovalStatus, LifecycleStatus
from apps.marketing.models import (
    Campaign,
    CampaignApprovalHistory,
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
    SocialPlatformDefinition,
    StreetAdLocation,
    StreetAdRecord,
    StreetAdTypeDefinition,
    StreetAdTypeLine,
    TVAdRecord,
    TVChannel,
)
from apps.marketing.services import CampaignApprovalService, CampaignBudgetService


class CampaignBudgetServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="marketing-acme")
        self.actor = User.objects.create_user(email="marketer@example.com")
        today = timezone.localdate()
        self.campaign = Campaign.objects.create(
            company=self.company,
            name="Launch",
            start_date=today,
            end_date=today + timedelta(days=10),
            created_by=self.actor,
        )

    def test_recalculate_includes_all_budget_sources(self):
        event = EventRecord.objects.create(campaign=self.campaign, name="Event", budget=Decimal("100.00"))
        EventCelebrity.objects.create(event=event, name="Speaker", budget=Decimal("20.00"))
        EventGiveaway.objects.create(event=event, name="Gift", budget=Decimal("30.00"))
        EventCatering.objects.create(event=event, name="Food", budget=Decimal("40.00"))
        EventPrintOut.objects.create(event=event, name="Flyers", budget=Decimal("10.00"))

        tv = TVAdRecord.objects.create(campaign=self.campaign, name="TV", budget=Decimal("200.00"))
        TVChannel.objects.create(tv_ad=tv, channel_name="Channel", budget=Decimal("50.00"))

        street = StreetAdRecord.objects.create(campaign=self.campaign, name="Street", budget=Decimal("300.00"))
        ad_type = StreetAdTypeDefinition.objects.create(code="BILLBOARD", name="Billboard")
        line = StreetAdTypeLine.objects.create(street_ad=street, ad_type=ad_type, budget=Decimal("60.00"))
        StreetAdLocation.objects.create(type_line=line, location_text="Road", budget=Decimal("70.00"))

        exhibition = ExhibitionRecord.objects.create(campaign=self.campaign, name="Expo", budget=Decimal("400.00"))
        ExhibitionCelebrity.objects.create(exhibition=exhibition, name="Guest", budget=Decimal("80.00"))
        ExhibitionGiveaway.objects.create(exhibition=exhibition, name="Bag", budget=Decimal("90.00"))
        ExhibitionCatering.objects.create(exhibition=exhibition, name="Coffee", budget=Decimal("100.00"))
        ExhibitionPrintOut.objects.create(exhibition=exhibition, name="Booklet", budget=Decimal("110.00"))

        social = SocialMediaAdRecord.objects.create(campaign=self.campaign, name="Social")
        platform = SocialPlatformDefinition.objects.create(code="META", name="Meta")
        SocialMediaPlatformLine.objects.create(social_ad=social, platform=platform, budget=Decimal("500.00"))

        OtherCost.objects.create(campaign=self.campaign, value=Decimal("25.00"), reason="Permit")

        total = CampaignBudgetService.recalculate(campaign=self.campaign, actor=self.actor)

        self.campaign.refresh_from_db()
        self.assertEqual(total, Decimal("2185.00"))
        self.assertEqual(self.campaign.total_budget, Decimal("2185.00"))
        snapshot = CampaignBudgetSnapshot.objects.get(campaign=self.campaign)
        self.assertEqual(snapshot.breakdown_json["events"], 200.0)
        self.assertEqual(snapshot.breakdown_json["tv_ads"], 250.0)
        self.assertEqual(snapshot.breakdown_json["street_ads"], 430.0)
        self.assertEqual(snapshot.breakdown_json["exhibition"], 780.0)
        self.assertEqual(snapshot.breakdown_json["social_media"], 500.0)
        self.assertEqual(snapshot.breakdown_json["other_costs"], 25.0)


class CampaignApprovalServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="approval-acme")
        self.actor = User.objects.create_user(email="finance@example.com")
        today = timezone.localdate()
        self.campaign = Campaign.objects.create(
            company=self.company,
            name="Review",
            start_date=today,
            end_date=today + timedelta(days=1),
            total_budget=Decimal("100.00"),
        )
        OtherCost.objects.create(campaign=self.campaign, value=Decimal("100.00"), reason="Media")

    def test_reason_is_required_for_semi_approved_and_not_approved(self):
        with self.assertRaises(ValidationError):
            CampaignApprovalService.set_status(
                campaign_id=self.campaign.id,
                status=ApprovalStatus.SEMI_APPROVED,
                actor=self.actor,
            )

        with self.assertRaises(ValidationError):
            CampaignApprovalService.set_status(
                campaign_id=self.campaign.id,
                status=ApprovalStatus.NOT_APPROVED,
                actor=self.actor,
            )

    def test_semi_approved_stores_rejected_budget_keys_and_history(self):
        CampaignApprovalService.set_status(
            campaign_id=self.campaign.id,
            status=ApprovalStatus.SEMI_APPROVED,
            actor=self.actor,
            reason="Partial approval",
            rejected_budgets=["other_costs.0"],
        )

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.approval_status, ApprovalStatus.SEMI_APPROVED)
        self.assertEqual(self.campaign.rejected_budgets, ["other_costs.0"])
        self.assertEqual(CampaignApprovalHistory.objects.get(campaign=self.campaign).to_status, ApprovalStatus.SEMI_APPROVED)

    def test_lifecycle_status_is_date_based_not_approval_based(self):
        today = timezone.localdate()
        future = Campaign.objects.create(
            company=self.company,
            name="Future",
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=2),
            approval_status=ApprovalStatus.APPROVED,
        )

        self.assertEqual(future.lifecycle_status, LifecycleStatus.COMING)
