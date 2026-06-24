"""Permission-aware templates (docs §4.5): {% if request.user|can:'code' %}."""
from django import template

from ..services import EffectivePermissionResolver

register = template.Library()


@register.filter(name="can")
def can(user, code: str) -> bool:
    return EffectivePermissionResolver.has(user, code)
