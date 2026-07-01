from django.core.cache import cache
from django.test import TestCase

from apps.companies.models import Company
from apps.companies.services import CurrentCompanyResolver, _cache_key
from apps.tenants.db import clear_current_db, set_current_db


class CurrentCompanyResolverTests(TestCase):
    def tearDown(self):
        clear_current_db()
        cache.clear()

    def test_default_company_uses_active_company_only(self):
        Company.objects.create(name="Inactive", slug="inactive", is_active=False)
        active = Company.objects.create(name="Active", slug="active")

        self.assertEqual(CurrentCompanyResolver.default_company(), active)

    def test_company_cache_key_is_tenant_scoped(self):
        set_current_db("tenant_first")
        first_key = _cache_key()

        set_current_db("tenant_second")
        second_key = _cache_key()

        self.assertEqual(first_key, "current_company:tenant_first")
        self.assertEqual(second_key, "current_company:tenant_second")
        self.assertNotEqual(first_key, second_key)
