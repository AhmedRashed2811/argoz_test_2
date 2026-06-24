"""CBV authorization mixin (docs §4.5)."""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied

from .services import EffectivePermissionResolver


class CRMPermissionRequiredMixin:
    """Set `required_permission = 'module.entity.action'` on the view."""

    required_permission: str | None = None

    def dispatch(self, request, *args, **kwargs):
        code = self.required_permission
        if code and not EffectivePermissionResolver.has(request.user, code):
            raise DjangoPermissionDenied(f"Missing permission: {code}")
        return super().dispatch(request, *args, **kwargs)
