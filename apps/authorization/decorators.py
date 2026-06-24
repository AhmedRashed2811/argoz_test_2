"""View-level authorization (docs §4.5). Thin: maps the custom permission check
to an HTTP 403, keeping role logic out of views."""
from functools import wraps

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied

from .services import EffectivePermissionResolver


def crm_permission_required(code: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not EffectivePermissionResolver.has(request.user, code):
                raise DjangoPermissionDenied(f"Missing permission: {code}")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
