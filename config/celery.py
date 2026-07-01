"""Celery app entry point (docs §12). Tasks live in each app's tasks.py and
only call services."""
import os

from celery import Celery
from celery.signals import before_task_publish, task_postrun, task_prerun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("argoz")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# ── Tenant context propagation (docs §15.1) ──────────────────────────────────
# A task enqueued inside a tenant request must run against that tenant's DB, not
# the control-plane `default`. The publisher stamps the active alias onto the
# message; the worker re-registers the connection (tenant aliases aren't in
# settings.DATABASES at boot) and pins the ORM to it for the task's duration.
# Beat-scheduled tasks carry no alias and stay on `default` — per-tenant fan-out
# for those is a separate piece, not wired here.
@before_task_publish.connect
def _stamp_tenant(headers=None, **_):
    from apps.tenants.db import get_current_db

    alias = get_current_db()
    if alias and headers is not None:
        headers["tenant_db"] = alias


@task_prerun.connect
def _enter_tenant(task=None, **_):
    alias = getattr(task.request, "tenant_db", None) if task else None
    if not alias:
        return
    from apps.tenants.db import ensure_connection, set_current_db
    from apps.tenants.models import Tenant

    tenant = Tenant.objects.using("default").filter(slug=alias.removeprefix("tenant_")).first()
    if tenant is not None:
        set_current_db(ensure_connection(tenant))


@task_postrun.connect
def _exit_tenant(**_):
    from apps.tenants.db import clear_current_db

    clear_current_db()
