"""Tenant routing for /t/<slug>/ paths.

Runs BEFORE SessionMiddleware/AuthenticationMiddleware so that session and user
lookups already hit the tenant's database. For a /t/<slug>/ request it:
  1. resolves the Tenant (in the control-plane DB),
  2. blocks if the subscription is inactive (data untouched),
  3. points the ORM at the tenant DB for this thread,
  4. sets the URL script prefix to /t/<slug>/ and strips it from path_info, so
     the existing root URLConf and every {% url %} keep working unchanged —
     reverse() automatically re-adds the /t/<slug>/ prefix.

Non-/t/ requests fall through to the control plane (default DB): the super-admin
panel and Django admin.
"""
from django.http import Http404
from django.shortcuts import render
from django.urls import set_script_prefix

from .db import clear_current_db, ensure_connection, set_current_db
from .models import Tenant

_PREFIX = "/t/"


class TenantRoutingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if not path.startswith(_PREFIX):
            if path == "/":
                from django.conf import settings
                from django.http import HttpResponseRedirect
                from .services import TenantService

                session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
                if session_key:
                    tenant = TenantService.find_tenant_by_session(session_key)
                    if tenant:
                        return HttpResponseRedirect(f"/t/{tenant.slug}/")
            return self.get_response(request)

        slug, _, _ = path[len(_PREFIX):].partition("/")
        if not slug:
            raise Http404("No tenant specified.")

        tenant = Tenant.objects.using("default").filter(slug=slug).first()
        if tenant is None:
            raise Http404("Unknown tenant.")
        if not tenant.is_active:
            return render(request, "tenants/suspended.html",
                          {"tenant": tenant}, status=403)

        set_current_db(ensure_connection(tenant))
        mount = f"/t/{slug}"
        set_script_prefix(mount + "/")
        # Resolver matches path_info (stripped); request.path stays full so
        # template {% if request.path == url %} active-state checks still match.
        request.path_info = path[len(mount):] or "/"
        try:
            return self.get_response(request)
        finally:
            clear_current_db()
