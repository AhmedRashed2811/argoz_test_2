from django.test import TestCase
from apps.companies.models import Company
from apps.authorization.models import RoleGroup, PermissionDefinition, UserPermissionOverride, Effect, RolePermission
from apps.accounts.services import UserService
from apps.accounts.models import User

class UserCreationPermissionsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Company", slug="test-company")
        
        # Create some test permissions
        self.perm_allow_role = PermissionDefinition.objects.create(
            code="test.allow_role", module="test", action="allow_role", name="Allow Role"
        )
        self.perm_deny_role = PermissionDefinition.objects.create(
            code="test.deny_role", module="test", action="deny_role", name="Deny Role"
        )
        self.perm_not_in_role = PermissionDefinition.objects.create(
            code="test.not_in_role", module="test", action="not_in_role", name="Not In Role"
        )
        
        # Create a test RoleGroup
        self.role = RoleGroup.objects.create(
            company=self.company, code="TEST_ROLE", name="Test Role"
        )
        
        # Associate permissions with the role
        RolePermission.objects.create(role=self.role, permission=self.perm_allow_role, allow=True)
        RolePermission.objects.create(role=self.role, permission=self.perm_deny_role, allow=True)

    def test_create_user_with_role_and_permission_overrides(self):
        # We submit:
        # 1. perm_allow_role (checked, and is in role -> no override needed)
        # 2. perm_not_in_role (checked, and NOT in role -> ALLOW override needed)
        # 3. perm_deny_role (unchecked, and is in role -> DENY override needed)
        submitted_codes = ["test.allow_role", "test.not_in_role"]
        
        user = UserService.create_user(
            company=self.company,
            email="testuser@example.com",
            password="testpassword123",
            default_role=self.role,
            first_name="Test",
            last_name="User",
            phone="12345678",
            permission_codes=submitted_codes
        )
        
        # Verify user is created
        self.assertEqual(user.email, "testuser@example.com")
        self.assertEqual(user.profile.default_role, self.role)
        
        # Verify overrides
        overrides = UserPermissionOverride.objects.filter(user=user)
        self.assertEqual(overrides.count(), 2)
        
        # Verify ALLOW override for perm_not_in_role
        allow_override = overrides.filter(permission=self.perm_not_in_role).first()
        self.assertIsNotNone(allow_override)
        self.assertEqual(allow_override.effect, Effect.ALLOW)
        
        # Verify DENY override for perm_deny_role
        deny_override = overrides.filter(permission=self.perm_deny_role).first()
        self.assertIsNotNone(deny_override)
        self.assertEqual(deny_override.effect, Effect.DENY)
