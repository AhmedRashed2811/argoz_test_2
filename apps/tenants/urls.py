"""Control-plane routes. Mounted at /tenant-admin/ (NOT under /t/), so these
always run against the default database."""
from django.urls import path

from . import views

app_name = "tenants"

urlpatterns = [
    path("", views.tenant_list, name="list"),
    path("api/", views.tenant_api_list, name="api_list"),
    path("api/create/", views.tenant_api_create, name="api_create"),
    path("<int:tenant_id>/api/toggle/", views.tenant_api_toggle, name="api_toggle"),
    path("<int:tenant_id>/api/update/", views.tenant_api_update, name="api_update"),
]
