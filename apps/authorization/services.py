"""Effective permission resolution (docs §4.3) + management writes. Centralized:
every protected view/service action checks codes through here, never role names."""
from __future__ import annotations

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
