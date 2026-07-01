from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.companies.models import Company
from apps.core.exceptions import ValidationError
from apps.finance.services import FinanceApprovalService
from apps.marketing.constants import ApprovalStatus
from apps.marketing.models import Campaign, OtherCost


class FinanceApprovalServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="finance-acme")
        self.actor = User.objects.create_user(email="finance@example.com")
        today = timezone.localdate()
        self.campaign = Campaign.objects.create(
            company=self.company,
            name="Finance Campaign",
            start_date=today,
            end_date=today + timedelta(days=5),
            total_budget=Decimal("100.00"),
        )
        OtherCost.objects.create(campaign=self.campaign, value=Decimal("40.00"), reason="Rejected line")

    def test_decide_rejects_unknown_frontend_status(self):
        with self.assertRaises(ValidationError):
            FinanceApprovalService.decide(
                campaign_id=self.campaign.id,
                js_status="unknown",
                actor=self.actor,
            )

    def test_approved_budget_is_zero_for_pending_or_rejected_campaigns(self):
        self.assertEqual(FinanceApprovalService.approved_budget(self.campaign), 0.0)

        self.campaign.approval_status = ApprovalStatus.NOT_APPROVED
        self.campaign.save(update_fields=["approval_status"])

        self.assertEqual(FinanceApprovalService.approved_budget(self.campaign), 0.0)

    def test_approved_budget_subtracts_rejected_lines_for_semi_approved_campaigns(self):
        self.campaign.approval_status = ApprovalStatus.SEMI_APPROVED
        self.campaign.total_budget = Decimal("100.00")
        self.campaign.rejected_budgets = ["other_costs.0"]
        self.campaign.save(update_fields=["approval_status", "total_budget", "rejected_budgets"])

        self.assertEqual(FinanceApprovalService.approved_budget(self.campaign), 60.0)
