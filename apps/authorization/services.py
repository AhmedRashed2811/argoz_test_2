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
                          created_by=None):
        obj, _ = UserPermissionOverride.objects.update_or_create(
            user=user, permission=permission, effect=effect,
            defaults={"reason": reason, "created_by": created_by},
        )
        EffectivePermissionResolver.invalidate(user.pk)
        return obj

    @staticmethod
    def assign_role(*, user, role, assigned_by=None):
        obj, _ = UserRole.objects.update_or_create(
            user=user, role=role, defaults={"is_active": True, "assigned_by": assigned_by}
        )
        EffectivePermissionResolver.invalidate(user.pk)
        return obj
