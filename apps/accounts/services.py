"""Accounts services (docs §15.1: workflows live here, not views). User-creation
wizard with role defaults is owned by the authorization app (§4.4)."""
from __future__ import annotations

from django.db import transaction

from .models import Team, TeamMember, User, UserProfile


class UserService:
    @staticmethod
    @transaction.atomic
    def create_user(*, company, email, password=None, default_role=None,
                    first_name="", last_name="", phone="", permission_codes=None,
                    created_by=None, request_meta=None, **profile):
        user = User.objects.create_user(
            email=email, password=password, first_name=first_name,
            last_name=last_name, phone=phone,
        )
        UserProfile.objects.create(
            user=user, company=company, default_role=default_role, **profile
        )
        # Assigning the default role seeds the user's permission baseline (§4.3).
        if default_role is not None:
            from apps.authorization.services import PermissionManagementService

            PermissionManagementService.assign_role(user=user, role=default_role, assigned_by=created_by, request_meta=request_meta, audit=False)

        # Determine and create overrides if custom permission_codes are provided
        if permission_codes is not None:
            from apps.authorization.services import PermissionManagementService
            PermissionManagementService.update_user_overrides(
                user=user,
                permission_codes=permission_codes,
                created_by=created_by,
                request_meta=request_meta,
                audit=False,
            )

        # Audit creation
        from apps.audit.services import AuditService, DiffService
        from apps.core.constants import AuditAction

        after_data = DiffService.snapshot(user, fields=["email", "first_name", "last_name", "phone", "is_active"])
        after_data.update(DiffService.snapshot(user.profile, fields=["job_title", "department", "availability_status"]))
        if default_role:
            after_data["default_role"] = default_role.name

        AuditService.log(
            action=AuditAction.CREATE, instance=user, actor=created_by, company=company,
            module="accounts", request_meta=request_meta,
            after=after_data, entity_display=user.email,
        )

        return user

    @staticmethod
    @transaction.atomic
    def update_user(*, user, email, password=None, default_role=None,
                    first_name="", last_name="", phone="", permission_codes=None,
                    created_by=None, request_meta=None, **profile_data):
        from apps.audit.services import AuditService, DiffService
        from apps.core.constants import AuditAction

        # Capture state before update
        before_data = DiffService.snapshot(user, fields=["email", "first_name", "last_name", "phone", "is_active"])
        before_data.update(DiffService.snapshot(user.profile, fields=["job_title", "department", "availability_status"]))
        if user.profile.default_role:
            before_data["default_role"] = user.profile.default_role.name

        user.email = email
        if password:
            user.set_password(password)
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.save()

        profile = user.profile
        profile.default_role = default_role
        for key, value in profile_data.items():
            setattr(profile, key, value)
        profile.save()

        from apps.authorization.models import UserRole
        if default_role is not None:
            from apps.authorization.services import PermissionManagementService
            PermissionManagementService.assign_role(user=user, role=default_role, assigned_by=created_by, request_meta=request_meta, audit=False)
        else:
            UserRole.objects.filter(user=user).update(is_active=False)

        if permission_codes is not None:
            from apps.authorization.services import PermissionManagementService
            PermissionManagementService.update_user_overrides(
                user=user,
                permission_codes=permission_codes,
                created_by=created_by,
                request_meta=request_meta,
                audit=True,
            )

        # Capture state after update
        after_data = DiffService.snapshot(user, fields=["email", "first_name", "last_name", "phone", "is_active"])
        after_data.update(DiffService.snapshot(user.profile, fields=["job_title", "department", "availability_status"]))
        if default_role:
            after_data["default_role"] = default_role.name

        AuditService.log(
            action=AuditAction.UPDATE, instance=user, actor=created_by, company=user.profile.company,
            module="accounts", request_meta=request_meta,
            before=before_data, after=after_data,
            entity_display=user.email,
        )
        return user

    @staticmethod
    @transaction.atomic
    def delete_user(*, user, actor=None, request_meta=None):
        user.is_active = False
        user.save()
        profile = user.profile
        profile.availability_status = "OFFLINE"
        profile.save()

        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        AuditService.log(
            action=AuditAction.DELETE, instance=user, actor=actor, company=profile.company,
            module="accounts", request_meta=request_meta,
            reason="Deactivated user profile",
            entity_display=user.email,
        )

    @staticmethod
    @transaction.atomic
    def activate_user(*, user, actor=None, request_meta=None):
        user.is_active = True
        user.save()
        profile = user.profile
        profile.availability_status = "AVAILABLE"
        profile.save()

        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        AuditService.log(
            action=AuditAction.UPDATE, instance=user, actor=actor, company=profile.company,
            module="accounts", request_meta=request_meta,
            reason="Activated user profile",
            after={"is_active": True, "availability_status": "AVAILABLE"},
            entity_display=user.email,
        )

    @staticmethod
    def get_user_creation_context(*, company):
        import json
        from apps.authorization.models import RoleGroup, PermissionDefinition, RolePermission

        roles = RoleGroup.objects.filter(company=company, is_active=True)
        permissions = PermissionDefinition.objects.filter(is_active=True).order_by("module", "code")
        
        role_permissions_map = {}
        for role in roles:
            allowed_codes = list(
                RolePermission.objects.filter(
                    role=role, allow=True, permission__is_active=True
                ).values_list("permission__code", flat=True)
            )
            role_permissions_map[str(role.id)] = allowed_codes
        role_permissions_json = json.dumps(role_permissions_map)
        
        return {
            "roles": roles,
            "permissions": permissions,
            "role_permissions_json": role_permissions_json,
        }


class TeamService:
    @staticmethod
    @transaction.atomic
    def add_member(*, team: Team, user: User, **kwargs) -> TeamMember:
        member, _ = TeamMember.objects.update_or_create(
            team=team, user=user, defaults=kwargs
        )
        return member


class AvailabilityService:
    @staticmethod
    def set_status(*, user: User, status: str) -> None:
        UserProfile.objects.filter(user=user).update(availability_status=status)
