"""Per-request tenant DB selection. The routing middleware sets the active
alias; the router (routers.py) reads it for every query. No alias set =>
control plane => Django falls back to `default`.

Uses a ContextVar (not threading.local) so the alias propagates into async
views and sync_to_async thread-pool executors (e.g. the notifications SSE
stream), which a threadlocal would not reach.

ponytail: Celery/async tasks run OUTSIDE the request and will hit `default`
unless given explicit tenant context — wire that in when per-tenant background
work is actually needed.
"""
from __future__ import annotations

from contextvars import ContextVar
from functools import wraps

from django.db import DEFAULT_DB_ALIAS, connections
from django.db import transaction as _transaction

_current_db: ContextVar[str | None] = ContextVar("current_db", default=None)


def set_current_db(alias: str | None) -> None:
    _current_db.set(alias)


def get_current_db() -> str | None:
    return _current_db.get()


def current_scope() -> str:
    """Stable per-tenant namespace for anything living in SHARED Redis (cache
    keys, channel-layer groups, pub/sub channels). Model PKs are per-tenant
    auto-increment, so user id 5 exists in every tenant DB — without this prefix
    two tenants collide on the same key/group and leak into each other. Falls
    back to 'default' (control plane) when no tenant is active."""
    return get_current_db() or "default"


def clear_current_db() -> None:
    _current_db.set(None)


_orig_atomic = _transaction.atomic


class _LazyAtomic:
    """Resolves the active tenant alias at __enter__ time (not construction), so
    `with transaction.atomic():` opens its transaction on the request's tenant DB."""

    def __init__(self, savepoint, durable):
        self._savepoint, self._durable, self._ctx = savepoint, durable, None

    def __enter__(self):
        self._ctx = _orig_atomic(
            get_current_db() or DEFAULT_DB_ALIAS, self._savepoint, self._durable
        )
        return self._ctx.__enter__()

    def __exit__(self, *exc):
        return self._ctx.__exit__(*exc)


def tenant_atomic(using=None, savepoint=True, durable=False):
    """Drop-in for transaction.atomic that targets the active tenant DB.

    Django binds the alias when atomic() is called — for a bare `@transaction.atomic`
    that's import time, before any tenant is active, so writes/select_for_update land
    on `default` while the router sends queries to the tenant alias (mismatch =>
    TransactionManagementError). Resolving the alias lazily (decorator: per call;
    context manager: per __enter__) fixes every call site at once. Explicit `using=`
    is honoured unchanged (e.g. provisioning writes to a specific alias)."""
    if callable(using):  # bare @transaction.atomic
        func = using

        @wraps(func)
        def inner(*a, **kw):
            with _orig_atomic(get_current_db() or DEFAULT_DB_ALIAS, savepoint, durable):
                return func(*a, **kw)

        return inner
    if using is None:
        return _LazyAtomic(savepoint, durable)
    return _orig_atomic(using, savepoint, durable)


def install_tenant_atomic() -> None:
    """Patch django.db.transaction.atomic (call sites use `transaction.atomic`,
    resolved at call time, so this one swap covers them all)."""
    _transaction.atomic = tenant_atomic


def ensure_connection(tenant) -> str:
    """Register the tenant's connection in the live connection handler (the DB
    is created at runtime, so it isn't in settings.DATABASES at boot). Returns
    the alias to route to."""
    alias = tenant.db_alias
    if alias not in connections.databases:
        connections.databases[alias] = tenant.connection_config()
    return alias
