"""Notification creation + fan-out (docs §12). Business services call the typed
helpers; delivery (websocket/email) is dispatched on commit via Celery (Phase 12
tasks). Channel selection follows the notification.delivery_policy (§7.2)."""
from __future__ import annotations

from django.db import transaction

from .constants import Channel, NotificationCode
from .models import Notification, NotificationDelivery, NotificationType


class NotificationService:
    @staticmethod
    def _type(code: str) -> NotificationType:
        ntype, _ = NotificationType.objects.get_or_create(
            code=code,
            defaults={"name": code.replace("_", " ").title(),
                      "default_channels": [Channel.IN_APP]},
        )
        return ntype

    @staticmethod
    def create(*, company, recipient, code: str, title: str = "", body: str = "",
               priority: str = "NORMAL", related_type: str = "", related_id: str = "",
               channels: list[str] | None = None) -> Notification | None:
        if recipient is None:
            return None
        ntype = NotificationService._type(code)
        notif = Notification.objects.create(
            company=company,
            recipient=recipient,
            notification_type=ntype,
            title=title or ntype.name,
            body=body,
            priority=priority,
            related_type=related_type,
            related_id=str(related_id),
        )
        for channel in (channels or ntype.default_channels or [Channel.IN_APP]):
            NotificationDelivery.objects.create(notification=notif, channel=channel)
        # Fan-out only after the surrounding business transaction commits (§6.2).
        transaction.on_commit(lambda: NotificationService._dispatch(notif.id))
        return notif

    @staticmethod
    def create_for_users(*, company, recipients, code, exclude_user=None, **kwargs):
        # The actor behind an event should not be notified about their own action
        # (e.g. a manager who creates a campaign — docs §12). Pass exclude_user.
        seen = set()
        if exclude_user is not None and getattr(exclude_user, "pk", None) is not None:
            seen.add(exclude_user.pk)
        for user in recipients:
            if user is None or user.pk in seen:
                continue
            seen.add(user.pk)
            NotificationService.create(
                company=company, recipient=user, code=code, **kwargs
            )

    @staticmethod
    def _dispatch(notification_id) -> None:
        # Lazy import: tasks module wires Celery in Phase 12; degrade to no-op
        # if the worker stack isn't importable in a given environment.
        try:
            from .tasks import fanout_notification

            fanout_notification.delay(str(notification_id))
        except Exception:  # ponytail: never let notify failure break the business txn
            pass

    # --- Typed convenience wrappers used across domains (docs §12.3) ---
    @staticmethod
    def lead_assigned(company, lead, salesman):
        NotificationService.create(
            company=company, recipient=salesman, code=NotificationCode.LEAD_ASSIGNED,
            title="New lead assigned", body=str(lead),
            related_type="Lead", related_id=lead.pk,
        )

    @staticmethod
    async def sse_stream(user):
        """Async generator that yields SSE-formatted lines for *user*."""
        import asyncio
        import json
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        channel_name = await layer.new_channel()
        await layer.group_add(f"notifications_{user.id}", channel_name)
        try:
            while True:
                try:
                    message = await asyncio.wait_for(layer.receive(channel_name), timeout=25)
                    yield f"data: {json.dumps(message.get('payload', {}))}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            await layer.group_discard(f"notifications_{user.id}", channel_name)

    @staticmethod
    def mark_read(*, notification: Notification) -> None:
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read", "updated_at"])

    @staticmethod
    def mark_all_read(*, recipient) -> int:
        return Notification.objects.filter(
            recipient=recipient, is_read=False
        ).update(is_read=True)
