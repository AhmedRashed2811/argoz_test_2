"""View-level authorization (docs §4.5). Thin: maps the custom permission check
to an HTTP 403, keeping role logic out of views."""
from functools import wraps

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied

from .services import EffectivePermissionResolver


def crm_permission_required(*codes: str):
    """Allow the view if the user has ANY of the given permission codes."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not any(EffectivePermissionResolver.has(request.user, c) for c in codes):
                raise DjangoPermissionDenied(f"Missing permission: {' / '.join(codes)}")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
