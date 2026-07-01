from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.accounts.models import Agency, Broker, User
from apps.accounts.services import AgencyService, BrokerService, UserService
from apps.authorization.models import RoleGroup
from apps.companies.models import Company


class UserServiceGuardTests(TestCase):
    def test_only_superuser_can_manage_their_own_superuser_account(self):
        actor = User.objects.create_user(email="admin@example.com")
        superuser = User.objects.create_superuser(email="root@example.com", password="pw")

        with self.assertRaises(PermissionDenied):
            UserService.assert_can_manage_user(actor, superuser)

        UserService.assert_can_manage_user(superuser, superuser)


class BrokerAndAgencyServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="accounts-acme")
        RoleGroup.objects.create(company=self.company, code="BROKERS", name="Brokers")

    def test_create_broker_creates_linked_user_when_email_is_supplied(self):
        broker = BrokerService.create_broker(
            company=self.company,
            name="External Broker",
            email="broker@example.com",
            password="password",
            phone="123",
        )

        self.assertIsNotNone(broker.linked_user)
        self.assertEqual(broker.linked_user.email, "broker@example.com")
        self.assertEqual(broker.linked_user.profile.company, self.company)

    def test_agency_update_syncs_denormalized_broker_company_name(self):
        agency = Agency.objects.create(company=self.company, name="Old Agency")
        broker = Broker.objects.create(
            company=self.company,
            agency=agency,
            name="Broker One",
            company_name="Old Agency",
        )

        AgencyService.update_agency(agency_id=agency.id, name="New Agency")

        broker.refresh_from_db()
        self.assertEqual(broker.company_name, "New Agency")

    def test_agency_delete_detaches_brokers(self):
        agency = Agency.objects.create(company=self.company, name="Delete Me")
        broker = Broker.objects.create(company=self.company, agency=agency, name="Broker One")

        AgencyService.delete_agency(agency_id=agency.id)

        broker.refresh_from_db()
        self.assertIsNone(broker.agency)
