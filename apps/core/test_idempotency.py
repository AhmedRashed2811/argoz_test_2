from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.core.middleware import IdempotencyMiddleware
from apps.tenants.db import clear_current_db, set_current_db


class IdempotencyMiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        clear_current_db()
        cache.clear()

    def test_successful_write_is_replayed_for_same_key(self):
        calls = {"count": 0}

        def view(request):
            calls["count"] += 1
            return HttpResponse(f"created-{calls['count']}", status=201)

        middleware = IdempotencyMiddleware(view)
        first = middleware(
            self.factory.post("/leads/create/", HTTP_X_IDEMPOTENCY_KEY="same-key")
        )
        second = middleware(
            self.factory.post("/leads/create/", HTTP_X_IDEMPOTENCY_KEY="same-key")
        )

        self.assertEqual(first.content, b"created-1")
        self.assertEqual(second.content, b"created-1")
        self.assertEqual(second["X-Idempotent-Replay"], "1")
        self.assertEqual(calls["count"], 1)

    def test_failed_write_is_not_cached(self):
        calls = {"count": 0}

        def view(request):
            calls["count"] += 1
            return HttpResponse(f"failed-{calls['count']}", status=500)

        middleware = IdempotencyMiddleware(view)
        first = middleware(
            self.factory.post("/leads/create/", HTTP_X_IDEMPOTENCY_KEY="retry")
        )
        second = middleware(
            self.factory.post("/leads/create/", HTTP_X_IDEMPOTENCY_KEY="retry")
        )

        self.assertEqual(first.content, b"failed-1")
        self.assertEqual(second.content, b"failed-2")
        self.assertEqual(calls["count"], 2)

    def test_same_key_is_isolated_between_tenant_scopes(self):
        calls = {"count": 0}

        def view(request):
            calls["count"] += 1
            return HttpResponse(f"tenant-{calls['count']}")

        middleware = IdempotencyMiddleware(view)

        set_current_db("tenant_a")
        first = middleware(
            self.factory.post("/leads/create/", HTTP_X_IDEMPOTENCY_KEY="shared")
        )

        set_current_db("tenant_b")
        second = middleware(
            self.factory.post("/leads/create/", HTTP_X_IDEMPOTENCY_KEY="shared")
        )

        set_current_db("tenant_a")
        third = middleware(
            self.factory.post("/leads/create/", HTTP_X_IDEMPOTENCY_KEY="shared")
        )

        self.assertEqual(first.content, b"tenant-1")
        self.assertEqual(second.content, b"tenant-2")
        self.assertEqual(third.content, b"tenant-1")
        self.assertEqual(third["X-Idempotent-Replay"], "1")
