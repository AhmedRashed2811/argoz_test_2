from django.test import TestCase

from apps.accounts.models import Broker, Team, TeamMember, User, UserProfile
from apps.authorization.models import PermissionDefinition, RoleGroup, RolePermission
from apps.authorization.services import PermissionManagementService
from apps.companies.models import Company
from apps.leads.constants import ActiveStatus
from apps.leads.models import Lead, LeadSourceDefinition, LeadStageDefinition
from apps.reports.selectors import active_lead_counts, leads_for_user


class ReportSelectorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="reports-acme")
        self.source = LeadSourceDefinition.objects.create(code="CALL_CENTER", name="Call Center")
        self.stage = LeadStageDefinition.objects.create(code="FRESH", name="Fresh")
        self.user = User.objects.create_user(email="user@example.com")
        self.other = User.objects.create_user(email="other@example.com")
        for user in (self.user, self.other):
            UserProfile.objects.create(user=user, company=self.company)
        self.team = Team.objects.create(company=self.company, name="Team")
        TeamMember.objects.create(team=self.team, user=self.user)

    def _grant(self, user, code):
        perm = PermissionDefinition.objects.create(
            code=code,
            module="leads",
            action=code.rsplit(".", 1)[-1],
            name=code,
        )
        role = RoleGroup.objects.create(company=self.company, code=code.upper().replace(".", "_"), name=code)
        RolePermission.objects.create(role=role, permission=perm)
        PermissionManagementService.assign_role(user=user, role=role, audit=False)

    def test_active_lead_counts_split_active_and_inactive(self):
        Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="Active",
            phone="1",
            active_status=ActiveStatus.ACTIVE,
        )
        Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="Inactive",
            phone="2",
            active_status=ActiveStatus.INACTIVE,
        )

        self.assertEqual(active_lead_counts(self.company), {"active": 1, "inactive": 1})

    def test_leads_for_user_defaults_to_own_and_broker_owned_records(self):
        broker = Broker.objects.create(
            company=self.company,
            linked_user=self.user,
            name="Broker",
        )
        own = Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="Own",
            phone="1",
            assigned_salesman=self.user,
        )
        broker_owned = Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="Broker owned",
            phone="2",
            broker_owner=broker,
        )
        Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="Other",
            phone="3",
            assigned_salesman=self.other,
        )

        self.assertEqual(set(leads_for_user(self.user, self.company)), {own, broker_owned})

    def test_view_all_permission_returns_all_company_leads(self):
        self._grant(self.user, "leads.lead.view_all")
        first = Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="One",
            phone="1",
        )
        second = Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="Two",
            phone="2",
        )

        self.assertEqual(set(leads_for_user(self.user, self.company)), {first, second})
