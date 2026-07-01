"""Routes every ORM query to the request's tenant database. Returning None
means "no opinion" so Django uses `default` — that is the control plane
(super-admin panel, the Tenant registry itself). One database is active per
request, so cross-DB relations never arise."""
from .db import get_current_db


class TenantRouter:
    def db_for_read(self, model, **hints):
        return get_current_db()

    def db_for_write(self, model, **hints):
        return get_current_db()

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Every database holds the full schema (control plane + each tenant).
        return True
