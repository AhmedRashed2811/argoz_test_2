"""Root URLConf. All app URLs are namespaced; templates use {% url 'ns:name' %}
(docs §1.1, §14). The integrations webhook receiver is an external integration
endpoint, not a frontend API (§1.1)."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.leads import api as leads_api

urlpatterns = [
    path("admin/", admin.site.urls),
    # External read-only leads API (Bearer / x-api-key). Reached per-tenant via
    # /t/<slug>/api/leads/... — tenant routing strips the prefix before matching.
    path("api/leads/", leads_api.api_salesman_leads, name="api_salesman_leads"),
    path("api/leads/<str:email>", leads_api.api_salesman_leads),
    # SaaS control plane (operator only, default DB). Not under /t/.
    path("tenant-admin/", include("apps.tenants.urls")),
    path("", include("apps.reports.urls")),                 # dashboard:index
    path("accounts/", include("apps.accounts.urls")),
    path("leads/", include("apps.leads.urls")),
    path("marketing/", include("apps.marketing.urls")),
    path("finance/", include("apps.finance.urls")),
    path("authorization/", include("apps.authorization.urls")),
    path("policies/", include("apps.policies.urls")),
    path("audit/", include("apps.audit.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("chat/", include("apps.chat.urls")),
    path("notebook/", include("apps.notebook.urls")),
    path("integrations/", include("apps.integrations.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
