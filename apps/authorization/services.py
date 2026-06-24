"""Effective permission resolution (docs §4.3) + management writes. Centralized:
every protected view/service action checks codes through here, never role names."""
from __future__ import annotations
from apps.authorization.models import RoleGroup

from django.db import transaction
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from apps.core.exceptions import PermissionDenied

from .models import (
    Effect,
    PermissionDefinition,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)

_CACHE_PREFIX = "effperm:"
_CACHE_TTL = 300


class EffectivePermissionResolver:
    """Resolves the effective permission code set for a user (docs §4.3):
    union of active role defaults + direct ALLOW, minus direct DENY. Cached
    per user; invalidated when roles/overrides/permissions change."""

    @staticmethod
    def _cache_key(user_id) -> str:
        return f"{_CACHE_PREFIX}{user_id}"

    @classmethod
    def get_codes(cls, user) -> set[str]:
        if not getattr(user, "is_authenticated", False):
            return set()
        key = cls._cache_key(user.pk)
        cached = cache.get(key)
        if cached is not None:
            return set(cached)
        codes = cls._compute(user)
        cache.set(key, list(codes), _CACHE_TTL)
        return codes

    @classmethod
    def _compute(cls, user) -> set[str]:
        # 1-2: union active default permissions from active roles.
        role_ids = UserRole.objects.filter(user=user, is_active=True).values_list(
            "role_id", flat=True
        )
        codes = set(
            RolePermission.objects.filter(
                role_id__in=role_ids, allow=True, permission__is_active=True
            ).values_list("permission__code", flat=True)
        )
        # 3-5: apply direct overrides; DENY wins.
        now = timezone.now()
        overrides = UserPermissionOverride.objects.filter(user=user).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        ).select_related("permission")
        allow = {o.permission.code for o in overrides if o.effect == Effect.ALLOW}
        deny = {o.permission.code for o in overrides if o.effect == Effect.DENY}
        codes |= allow
        codes -= deny
        return codes

    @classmethod
    def has(cls, user, code: str) -> bool:
        if getattr(user, "is_superuser", False):
            return True  # technical emergency account only (docs §4.1)
        return code in cls.get_codes(user)

    @classmethod
    def require(cls, user, code: str, company=None) -> None:
        if not cls.has(user, code):
            raise PermissionDenied(f"Missing permission: {code}")

    @classmethod
    def invalidate(cls, user_id=None) -> None:
        if user_id is not None:
            cache.delete(cls._cache_key(user_id))
        else:
            # ponytail: no bulk-key delete on django-redis without scan; callers
            # pass user_id. Add a version key if global invalidation is needed.
            pass


# Public façade used by decorators/mixins/services/templates.
PermissionService = EffectivePermissionResolver


class PermissionManagementService:
    """UI-driven permission changes (docs §4.4). Audits + cache invalidation are
    wired by callers/signals (§17: permission change invalidates cache)."""

    @staticmethod
    def get_permission_catalog():
        return PermissionDefinition.objects.all().order_by("module", "code")

    @staticmethod
    def get_active_permissions():
        return PermissionDefinition.objects.filter(is_active=True).order_by("module", "code")

    @staticmethod
    def set_user_override(*, user, permission: PermissionDefinition, effect, reason="",
                          created_by=None, request_meta=None, audit=True):
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        existing = UserPermissionOverride.objects.filter(user=user, permission=permission, effect=effect).first()
        before_data = {
            "user_id": user.pk,
            "user": user.email,
            "permission": permission.code,
            "effect": existing.effect,
            "reason": existing.reason,
        } if existing else None

        obj, _ = UserPermissionOverride.objects.update_or_create(
            user=user, permission=permission, effect=effect,
            defaults={"reason": reason, "created_by": created_by},
        )
        EffectivePermissionResolver.invalidate(user.pk)

        after_data = {
            "user_id": user.pk,
            "user": user.email,
            "permission": permission.code,
            "effect": effect,
            "reason": reason,
        }
        
        company = None
        if hasattr(user, "profile") and user.profile:
            company = user.profile.company

        if audit:
            AuditService.log(
                action=AuditAction.PERMISSION_CHANGE,
                instance=obj,
                actor=created_by,
                company=company,
                module="authorization",
                before=before_data,
                after=after_data,
                reason=reason,
                request_meta=request_meta,
                entity_display=f"{user.get_full_name() or user.email}",
            )
        return obj

    @staticmethod
    def assign_role(*, user, role, assigned_by=None, request_meta=None, audit=True):
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        existing = UserRole.objects.filter(user=user, role=role).first()
        before_data = {
            "user_id": user.pk,
            "user": user.email,
            "role": role.name,
            "is_active": existing.is_active,
        } if existing else None

        obj, _ = UserRole.objects.update_or_create(
            user=user, role=role, defaults={"is_active": True, "assigned_by": assigned_by}
        )
        EffectivePermissionResolver.invalidate(user.pk)

        after_data = {
            "user_id": user.pk,
            "user": user.email,
            "role": role.name,
            "is_active": True,
        }

        company = None
        if hasattr(user, "profile") and user.profile:
            company = user.profile.company

        if audit:
            AuditService.log(
                action=AuditAction.PERMISSION_CHANGE,
                instance=obj,
                actor=assigned_by,
                company=company,
                module="authorization",
                before=before_data,
                after=after_data,
                request_meta=request_meta,
                entity_display=f"{user.get_full_name() or user.email}",
            )
        return obj

    @staticmethod
    def update_user_overrides(*, user, permission_codes, created_by=None, request_meta=None, audit=True):
        from apps.authorization.models import PermissionDefinition, RolePermission, UserPermissionOverride, Effect
        from apps.authorization.services import PermissionService
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        # 1. Snapshot existing overrides
        existing_overrides_dict = {
            ov.permission.code: ov.effect 
            for ov in UserPermissionOverride.objects.filter(user=user).select_related("permission")
        }

        default_role = None
        if hasattr(user, "profile") and user.profile:
            default_role = user.profile.default_role

        role_perms = set()
        if default_role is not None:
            role_perms = set(
                RolePermission.objects.filter(
                    role=default_role, allow=True, permission__is_active=True
                ).values_list("permission__code", flat=True)
            )

        all_perms = PermissionDefinition.objects.filter(is_active=True)
        submitted_set = set(permission_codes)
        for perm in all_perms:
            code = perm.code
            is_checked = code in submitted_set
            is_in_role = code in role_perms

            # Determine target effect
            if is_checked and not is_in_role:
                target_effect = Effect.ALLOW
            elif not is_checked and is_in_role:
                target_effect = Effect.DENY
            else:
                target_effect = None

            # Find any existing overrides for this permission
            existing_overrides = list(UserPermissionOverride.objects.filter(user=user, permission=perm))

            if target_effect is not None:
                # Clean up overrides with a different effect silently
                for old_ov in existing_overrides:
                    if old_ov.effect != target_effect:
                        old_ov.delete()
                # Create or update the target override silently (audit=False)
                PermissionManagementService.set_user_override(
                    user=user, permission=perm, effect=target_effect,
                    reason="Customized at user matrix update" if audit else "Customized at user creation",
                    created_by=created_by, request_meta=request_meta, audit=False
                )
            else:
                # Target is None: delete any existing overrides silently
                for old_ov in existing_overrides:
                    old_ov.delete()

        PermissionService.invalidate(user.pk)

        # 2. Snapshot new overrides and log only once
        new_overrides_dict = {
            ov.permission.code: ov.effect 
            for ov in UserPermissionOverride.objects.filter(user=user).select_related("permission")
        }

        if audit and existing_overrides_dict != new_overrides_dict:
            company = user.profile.company if hasattr(user, "profile") and user.profile else None
            AuditService.log(
                action=AuditAction.PERMISSION_CHANGE,
                entity_type="UserPermissionOverride",
                entity_id=str(user.pk),
                actor=created_by,
                company=company,
                module="authorization",
                before=existing_overrides_dict,
                after=new_overrides_dict,
                request_meta=request_meta,
                entity_display=user.email,
            )


class RoleService:
    @staticmethod
    def get_roles_for_company(company):
        from django.db.models import Count, Q
        return (
            RoleGroup.objects.filter(company=company)
            .annotate(member_count=Count("assignments", filter=Q(assignments__is_active=True)))
            .order_by("name")
        )

    @staticmethod
    @transaction.atomic
    def create_role(*, company, code, name, description="", is_active=True, permission_ids=None, actor=None, request_meta=None) -> RoleGroup:
        role = RoleGroup.objects.create(
            company=company,
            code=code,
            name=name,
            description=description,
            is_active=is_active,
        )
        if permission_ids:
            for pid in permission_ids:
                RolePermission.objects.create(role=role, permission_id=pid, allow=True)

        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction
        AuditService.log(
            action=AuditAction.CREATE, instance=role, actor=actor, company=company,
            module="authorization", request_meta=request_meta,
            after={
                "code": code,
                "name": name,
                "description": description,
                "is_active": is_active,
                "permissions": list(RolePermission.objects.filter(role=role, allow=True).values_list("permission__code", flat=True)),
            },
            entity_display=name,
        )
        return role

    @staticmethod
    @transaction.atomic
    def update_role(*, role: RoleGroup, code, name, description="", is_active=True, permission_ids=None, actor=None, request_meta=None) -> RoleGroup:
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        before_data = {
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "is_active": role.is_active,
            "permissions": list(role.permissions.filter(allow=True).values_list("permission__code", flat=True)),
        }

        role.code = code
        role.name = name
        role.description = description
        role.is_active = is_active
        role.save()

        if not role.is_system_default:
            if permission_ids is not None:
                # Sync permissions
                existing_pids = set(role.permissions.values_list("permission_id", flat=True))
                target_pids = set(permission_ids)

                # Delete removed ones
                role.permissions.filter(permission_id__in=existing_pids - target_pids).delete()

                # Add new ones
                for pid in target_pids - existing_pids:
                    RolePermission.objects.create(role=role, permission_id=pid, allow=True)

        after_data = {
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "is_active": role.is_active,
            "permissions": list(role.permissions.filter(allow=True).values_list("permission__code", flat=True)),
        }

        AuditService.log(
            action=AuditAction.UPDATE, instance=role, actor=actor, company=role.company,
            module="authorization", request_meta=request_meta,
            before=before_data, after=after_data,
            entity_display=role.name,
        )
        return role

    @staticmethod
    @transaction.atomic
    def toggle_role(*, role: RoleGroup, actor=None, request_meta=None) -> bool:
        if role.is_system_default:
            raise ValueError("System default roles cannot be deactivated.")
        
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        before_active = role.is_active
        role.is_active = not role.is_active
        role.save()

        AuditService.log(
            action=AuditAction.UPDATE, instance=role, actor=actor, company=role.company,
            module="authorization", request_meta=request_meta,
            before={"is_active": before_active},
            after={"is_active": role.is_active},
            entity_display=role.name,
            reason="Toggled role active state",
        )
        return role.is_active
