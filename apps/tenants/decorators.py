"""Control-plane gate. The SaaS panel is the operator's own surface, separate
from per-tenant RBAC, so it keys on Django's is_superuser (the operator account
in the default DB) rather than the CRM authorization layer."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def superadmin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_superuser:
            raise PermissionDenied("Super-admin access only.")
        return view_func(request, *args, **kwargs)

    return _wrapped
