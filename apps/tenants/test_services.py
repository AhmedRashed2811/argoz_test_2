from django.test import TestCase

from apps.tenants.models import Tenant
from apps.tenants.services import TenantError, TenantProvisioningService, TenantService


class TenantServiceTests(TestCase):
    def test_validate_slug_normalizes_valid_slug(self):
        self.assertEqual(TenantProvisioningService._validate_slug(" Acme-1 "), "acme-1")

    def test_validate_slug_rejects_invalid_slug(self):
        with self.assertRaises(TenantError):
            TenantProvisioningService._validate_slug("Bad Slug!")

    def test_validate_slug_rejects_duplicate_slug(self):
        Tenant.objects.create(name="Acme", slug="acme", db_name="argoz_acme")

        with self.assertRaises(TenantError):
            TenantProvisioningService._validate_slug("acme")

    def test_set_active_toggles_subscription_gate_without_deleting_tenant(self):
        tenant = Tenant.objects.create(name="Acme", slug="acme", db_name="argoz_acme")

        TenantService.set_active(tenant, active=False)

        tenant.refresh_from_db()
        self.assertFalse(tenant.is_active)
        self.assertTrue(Tenant.objects.filter(slug="acme").exists())
