"""Invalidate the effective-permission cache whenever role/override data changes
(docs §17: permission changes must invalidate cache). Lightweight hook only —
audit of permission edits is written by the management service for semantic
context (§6.2)."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import RolePermission, UserPermissionOverride, UserRole
from .services import EffectivePermissionResolver


@receiver([post_save, post_delete], sender=UserRole)
@receiver([post_save, post_delete], sender=UserPermissionOverride)
def _invalidate_user(sender, instance, **kwargs):
    EffectivePermissionResolver.invalidate(instance.user_id)


@receiver([post_save, post_delete], sender=RolePermission)
def _invalidate_role(sender, instance, **kwargs):
    # Role default changed: invalidate every user holding that role.
    user_ids = UserRole.objects.filter(
        role_id=instance.role_id, is_active=True
    ).values_list("user_id", flat=True)
    for uid in user_ids:
        EffectivePermissionResolver.invalidate(uid)
