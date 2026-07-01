"""Cross-cutting idempotency for data-modifying requests (POST/PUT/PATCH).

A client sends a stable `idempotency_key` (UUID v4) either as a form field or
the `X-Idempotency-Key` header. The first request runs normally; its response
is cached under `crm_idempotency_key_<key>`. Any retry with the same key
(double-click, network-drop retry) replays the cached response instead of
re-executing the view — so leads/payments/etc. are never created twice.

Atomicity of the underlying writes is guaranteed separately by
DATABASES['default']['ATOMIC_REQUESTS'] = True, which wraps each request in a
transaction.
"""
from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect

CACHE_PREFIX = "crm_idempotency_key_"
CACHE_TIMEOUT = 60 * 12  # 12 minutes
_WRITE_METHODS = {"POST", "PUT", "PATCH"}


def _extract_key(request):
    key = request.headers.get("X-Idempotency-Key")
    if not key and request.method in _WRITE_METHODS:
        # Accessing POST here is safe; CSRF middleware already parsed it.
        key = request.POST.get("idempotency_key")
    return (key or "").strip() or None


class IdempotencyMiddleware:
    """Replay cached responses for repeated idempotency keys."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in _WRITE_METHODS:
            return self.get_response(request)

        key = _extract_key(request)
        if not key:
            return self.get_response(request)

        # Scope by tenant: the key is client-supplied, so two tenants could send
        # the same value and replay each other's cached response.
        from apps.tenants.db import current_scope

        cache_key = f"{CACHE_PREFIX}{current_scope()}:{key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return self._rebuild(cached)

        response = self.get_response(request)

        # Only cache definitive successes (2xx) and redirects (3xx, e.g. the
        # PRG pattern after a successful create). Errors stay retryable.
        if 200 <= response.status_code < 400:
            cache.set(cache_key, self._snapshot(response), CACHE_TIMEOUT)
        return response

    @staticmethod
    def _snapshot(response):
        return {
            "status": response.status_code,
            "content": response.content,
            "content_type": response.get("Content-Type", "text/html"),
            "location": response.get("Location"),
        }

    @staticmethod
    def _rebuild(data):
        if data["location"]:
            return HttpResponseRedirect(data["location"])
        resp = HttpResponse(
            data["content"],
            status=data["status"],
            content_type=data["content_type"],
        )
        resp["X-Idempotent-Replay"] = "1"
        return resp
