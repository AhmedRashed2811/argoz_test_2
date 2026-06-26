from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta

from apps.companies.models import Company
from apps.accounts.models import User, UserProfile, Team, TeamMember, Language, Broker
from apps.leads.models import Lead, Client, SLAInstance, WalkInQueueEntry, Reminder
from apps.leads.constants import StageCode, SourceCode, Origin, ActiveStatus, SLAStatus
from apps.leads.services import LeadCreationService, WalkInService, SLAService
from apps.distribution.services import SLAExpiryService, DistributionEngine
from apps.policies.models import CompanyPolicyValue, PolicyDefinition
from apps.policies.constants import PolicyCode


class CRMTechnicalAlignmentTests(TestCase):
    def setUp(self):
        # Seed stage, source, and policy configurations
        call_command("seed_crm")
        self.company = Company.objects.get(slug="argoz")
        self.arabic = Language.objects.create(code="ar", name="Arabic")

        # Create test users and profiles
        self.sales1 = User.objects.create_user(email="sales1@example.com", password="password", first_name="Sales", last_name="One")
        self.profile1 = UserProfile.objects.create(user=self.sales1, company=self.company, availability_status="AVAILABLE")

        # Assign SYSTEM_ADMINS role to sales1 so they are authorized for manual distribution
        from apps.authorization.models import RoleGroup
        from apps.authorization.services import PermissionManagementService
        admin_role = RoleGroup.objects.get(company=self.company, code="SYSTEM_ADMINS")
        PermissionManagementService.assign_role(user=self.sales1, role=admin_role)

        self.sales2 = User.objects.create_user(email="sales2@example.com", password="password", first_name="Sales", last_name="Two")
        self.profile2 = UserProfile.objects.create(user=self.sales2, company=self.company, availability_status="AVAILABLE")

        # Create teams
        self.team1 = Team.objects.create(company=self.company, name="Team 1", sales_head=self.sales1, order_index=1)
        self.team2 = Team.objects.create(company=self.company, name="Team 2", sales_head=self.sales2, order_index=2)

        # Team memberships
        self.tm1 = TeamMember.objects.create(team=self.team1, user=self.sales1, is_available=True)
        self.tm2 = TeamMember.objects.create(team=self.team2, user=self.sales2, is_available=True)

    def test_fresh_lead_sla_prioritization(self):
        # Policy is argoz defaults (Direct SLA is 2 hours, Broker SLA is 4 hours, Fresh SLA is 2 hours)
        pd_direct = PolicyDefinition.objects.get(code=PolicyCode.DIRECT_SLA)
        CompanyPolicyValue.objects.update_or_create(company=self.company, policy=pd_direct, defaults={"value_json": {"hours": 2}})
        pd_broker = PolicyDefinition.objects.get(code=PolicyCode.BROKER_SLA)
        CompanyPolicyValue.objects.update_or_create(company=self.company, policy=pd_broker, defaults={"value_json": {"hours": 4}})
        # 1. Direct lead
        lead_direct = LeadCreationService.create(
            company=self.company,
            source_code=SourceCode.CALL_CENTER,
            name="Direct Test Lead",
            phone="12345678",
            origin=Origin.DIRECT,
            language=self.arabic,
            assigned_salesman=self.sales1,
            campaign=None,
            auto_distribute=False,
        )
        # deadline should be approx 2 hours from now
        self.assertIsNotNone(lead_direct.sla_deadline)
        diff_hours = (lead_direct.sla_deadline - timezone.now()).total_seconds() / 3600.0
        self.assertAlmostEqual(diff_hours, 2.0, delta=0.1)

        # 2. Broker lead
        # Set Broker SLA to 4 hours in policy
        lead_broker = LeadCreationService.create(
            company=self.company,
            source_code=SourceCode.CALL_CENTER,
            name="Broker Test Lead",
            phone="87654321",
            origin=Origin.BROKER,
            language=self.arabic,
            assigned_salesman=self.sales1,
            campaign=None,
            auto_distribute=False,
        )
        # deadline should be approx 4 hours from now
        self.assertIsNotNone(lead_broker.sla_deadline)
        diff_hours_broker = (lead_broker.sla_deadline - timezone.now()).total_seconds() / 3600.0
        self.assertAlmostEqual(diff_hours_broker, 4.0, delta=0.1)

    def test_existing_client_source_auto_assign(self):
        # Create client record first
        Client.objects.create(
            company=self.company,
            name="Existing Client",
            phone="11112222",
            original_salesman=self.sales2,
            status="ACTIVE",
        )

        # Create lead from EXISTING_CLIENT source
        lead = LeadCreationService.create(
            company=self.company,
            source_code=SourceCode.EXISTING_CLIENT,
            name="Existing Client",
            phone="11112222",
            language=self.arabic,
        )
        # It should automatically assign to sales2 and auto_distribute is bypassed
        self.assertEqual(lead.assigned_salesman, self.sales2)

    def test_walkin_full_rotation_uses_by_turn(self):
        # Seed user languages so they are eligible for ar default language
        from apps.accounts.models import UserLanguage
        UserLanguage.objects.create(user=self.sales1, language=self.arabic, is_primary=True)
        UserLanguage.objects.create(user=self.sales2, language=self.arabic, is_primary=True)

        # Configure walk-in reception policy to FULL_ROTATION
        policy_def = PolicyDefinition.objects.get(code=PolicyCode.WALKIN_RECEPTION_POLICY)
        val = CompanyPolicyValue.objects.get(company=self.company, policy=policy_def)
        val.selected_option = policy_def.options.get(code="FULL_ROTATION")
        val.save()

        # Register two walkins. Under FULL_ROTATION, By Turn should sequentially rotate.
        # Since By Turn sequential fixed rotation pointer starts at 0:
        # First walk-in goes to tm1 (sales1) or tm2 (sales2) depending on eligible list sorting.
        # But it should be sequential!
        lead1 = WalkInService.register(
            company=self.company,
            name="Walkin 1",
            phone="33334444",
            how_did_you_know="WEBSITE",
            receptionist=self.sales1,
        )
        lead2 = WalkInService.register(
            company=self.company,
            name="Walkin 2",
            phone="55556666",
            how_did_you_know="WEBSITE",
            receptionist=self.sales1,
        )
        self.assertIsNotNone(lead1.assigned_salesman)
        self.assertIsNotNone(lead2.assigned_salesman)
        self.assertNotEqual(lead1.assigned_salesman, lead2.assigned_salesman)

    def test_walkin_team_turn_skips_empty_teams(self):
        # Team 1 has sales1 available
        # Team 2 has sales2 available. Let's make sales2 unavailable!
        self.tm2.is_available = False
        self.tm2.save()

        # Configure walk-in reception policy to TEAM_TURN
        policy_def = PolicyDefinition.objects.get(code=PolicyCode.WALKIN_RECEPTION_POLICY)
        val = CompanyPolicyValue.objects.get(company=self.company, policy=policy_def)
        val.selected_option = policy_def.options.get(code="TEAM_TURN")
        val.save()

        # Register a walk-in. If it was Team 2's turn, it should skip Team 2 and assign to Team 1
        # Let's seed rotation pointer to index 1 (which corresponds to Team 2 if Team 1 is index 0)
        from apps.distribution.models import RotationPointer
        RotationPointer.objects.create(
            company=self.company, pointer_code="WALKIN_TEAM_TURN", scope="GLOBAL", current_index=1
        )

        lead = WalkInService.register(
            company=self.company,
            name="Walkin 3",
            phone="77778888",
            how_did_you_know="WEBSITE",
            receptionist=self.sales1,
        )
        # It must be assigned to Team 1 (since Team 2 had no available salesmen)
        self.assertEqual(lead.assigned_team, self.team1)

    def test_broker_lead_sla_expiry_forces_manual(self):
        # Create a Broker lead with an active SLA
        lead = LeadCreationService.create(
            company=self.company,
            source_code=SourceCode.CALL_CENTER,
            name="Broker SLA Lead",
            phone="99990000",
            origin=Origin.BROKER,
            language=self.arabic,
            assigned_salesman=self.sales1,
            campaign=None,
            auto_distribute=False,
        )
        sla_inst = SLAInstance.objects.get(lead=lead, status=SLAStatus.ACTIVE)

        # Trigger SLA expiry processing. Under argoz default policy SLAExpiryMethod is ROUND_ROBIN.
        # But because origin is BROKER, process_instance must override it to MANUAL reassignment.
        SLAExpiryService.process_instance(sla_inst, task_id="test_task")

        # Refetch lead and check that it was NOT automatically redistributed
        lead.refresh_from_db()
        self.assertEqual(lead.assigned_salesman, self.sales1) # Still assigned to original salesman
        # SLA status should be breached
        sla_inst.refresh_from_db()
        self.assertEqual(sla_inst.status, SLAStatus.BREACHED)

        # There should be a manual distribution notification
        from apps.notifications.models import Notification
        from apps.notifications.constants import NotificationCode
        notif = Notification.objects.filter(
            company=self.company, notification_type__code=NotificationCode.MANUAL_DISTRIBUTION_REQUIRED
        ).first()
        self.assertIsNotNone(notif)
