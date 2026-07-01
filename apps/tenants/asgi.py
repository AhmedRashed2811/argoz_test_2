"""Tenant DB selection for WebSocket connections — the ASGI analogue of
TenantRoutingMiddleware (middleware.py only runs for HTTP, never for Channels).

WS paths arrive as /t/<slug>/ws/...  ; this strips the prefix and points the ORM
at the tenant DB BEFORE AuthMiddlewareStack runs, so the session/user lookup (and
every consumer query) hits the tenant database instead of the control-plane
`default`. Without it, lookups miss the user's session and the consumer rejects
the connection with 403.

Unknown/suspended slug => no DB set => AuthMiddleware sees AnonymousUser =>
consumer closes. That's the intended deny.
"""
from __future__ import annotations

from channels.db import database_sync_to_async

from .db import ensure_connection, set_current_db
from .models import Tenant

_PREFIX = "/t/"


def _split_tenant(path: str) -> tuple[str | None, str]:
    """('/t/acme/ws/chat/') -> ('acme', '/ws/chat/'); non-tenant -> (None, path)."""
    if not path.startswith(_PREFIX):
        return None, path
    slug, _, rest = path[len(_PREFIX):].partition("/")
    return (slug or None), ("/" + rest)


class TenantDBMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        slug, rest = _split_tenant(scope.get("path", ""))
        if slug:
            tenant = await self._get_tenant(slug)
            if tenant is not None:
                set_current_db(ensure_connection(tenant))
                scope = dict(scope, path=rest)
        return await self.inner(scope, receive, send)

    @staticmethod
    @database_sync_to_async
    def _get_tenant(slug):
        return Tenant.objects.using("default").filter(slug=slug, is_active=True).first()


def demo():
    assert _split_tenant("/t/acme/ws/chat/") == ("acme", "/ws/chat/")
    assert _split_tenant("/ws/chat/") == (None, "/ws/chat/")
    assert _split_tenant("/t//ws/chat/") == (None, "/ws/chat/")


if __name__ == "__main__":
    demo()
