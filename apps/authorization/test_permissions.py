from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.authorization.models import (
    Effect,
    PermissionDefinition,
    RoleGroup,
    RolePermission,
    UserPermissionOverride,
)
from apps.authorization.services import (
    EffectivePermissionResolver,
    PermissionManagementService,
)
from apps.companies.models import Company
from apps.tenants.db import clear_current_db, set_current_db


class EffectivePermissionResolverTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(name="Acme", slug="auth-acme")
        self.user = User.objects.create_user(email="agent@example.com")
        UserProfile.objects.create(user=self.user, company=self.company)
        self.role = RoleGroup.objects.create(company=self.company, code="SALES", name="Sales")
        self.role_perm = PermissionDefinition.objects.create(
            code="leads.lead.view_own", module="leads", action="view_own", name="View own"
        )
        self.extra_perm = PermissionDefinition.objects.create(
            code="reports.team.view", module="reports", action="view_team", name="Team report"
        )
        self.denied_perm = PermissionDefinition.objects.create(
            code="leads.lead.assign_manual", module="leads", action="assign_manual", name="Assign"
        )
        RolePermission.objects.create(role=self.role, permission=self.role_perm)
        RolePermission.objects.create(role=self.role, permission=self.denied_perm)
        PermissionManagementService.assign_role(user=self.user, role=self.role, audit=False)

    def tearDown(self):
        clear_current_db()
        cache.clear()

    def test_anonymous_user_has_no_effective_permissions(self):
        self.assertEqual(EffectivePermissionResolver.get_codes(AnonymousUser()), set())

    def test_superuser_has_any_permission_without_role_membership(self):
        admin = User.objects.create_superuser(email="root@example.com", password="password")
        self.assertTrue(EffectivePermissionResolver.has(admin, "any.code"))

    def test_role_defaults_allow_override_and_deny_override_are_resolved(self):
        UserPermissionOverride.objects.create(user=self.user, permission=self.extra_perm, effect=Effect.ALLOW)
        UserPermissionOverride.objects.create(user=self.user, permission=self.denied_perm, effect=Effect.DENY)

        codes = EffectivePermissionResolver.get_codes(self.user)

        self.assertIn("leads.lead.view_own", codes)
        self.assertIn("reports.team.view", codes)
        self.assertNotIn("leads.lead.assign_manual", codes)

    def test_expired_override_is_ignored(self):
        UserPermissionOverride.objects.create(
            user=self.user,
            permission=self.extra_perm,
            effect=Effect.ALLOW,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertNotIn("reports.team.view", EffectivePermissionResolver.get_codes(self.user))

    def test_permission_cache_is_namespaced_by_tenant_scope(self):
        set_current_db("tenant_alpha")
        cache.set(EffectivePermissionResolver._cache_key(self.user.pk), ["alpha.only"])

        set_current_db("tenant_beta")
        cache.set(EffectivePermissionResolver._cache_key(self.user.pk), ["beta.only"])

        set_current_db("tenant_alpha")
        self.assertEqual(EffectivePermissionResolver.get_codes(self.user), {"alpha.only"})

        set_current_db("tenant_beta")
        self.assertEqual(EffectivePermissionResolver.get_codes(self.user), {"beta.only"})


class PermissionMatrixTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="matrix-acme")
        self.user = User.objects.create_user(email="matrix@example.com")
        self.role = RoleGroup.objects.create(company=self.company, code="OPS", name="Operations")
        UserProfile.objects.create(user=self.user, company=self.company, default_role=self.role)
        self.role_perm = PermissionDefinition.objects.create(
            code="admin.users.access", module="admin", action="access", name="Users page"
        )
        self.extra_perm = PermissionDefinition.objects.create(
            code="audit.view_all", module="audit", action="view_all", name="Audit all"
        )
        RolePermission.objects.create(role=self.role, permission=self.role_perm)

    def test_update_user_overrides_writes_differences_from_default_role(self):
        PermissionManagementService.update_user_overrides(
            user=self.user,
            permission_codes=["audit.view_all"],
            audit=False,
        )

        overrides = {
            ov.permission.code: ov.effect
            for ov in UserPermissionOverride.objects.filter(user=self.user)
        }
        self.assertEqual(
            overrides,
            {"admin.users.access": Effect.DENY, "audit.view_all": Effect.ALLOW},
        )

    def test_update_user_overrides_removes_stale_overrides_when_back_to_default(self):
        PermissionManagementService.update_user_overrides(
            user=self.user, permission_codes=["audit.view_all"], audit=False
        )

        PermissionManagementService.update_user_overrides(
            user=self.user, permission_codes=["admin.users.access"], audit=False
        )

        self.assertFalse(UserPermissionOverride.objects.filter(user=self.user).exists())
