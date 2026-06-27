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
        try:
            from .tasks import fanout_notification

            fanout_notification(notification_id)
        except Exception:
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
        """Async generator that yields SSE-formatted lines for *user*.

        Uses Redis pub/sub directly (bypasses channels_redis) so messages
        published by fanout_notification in the Celery worker are received
        immediately without cross-process channel-layer timing issues.
        """
        import asyncio
        import json
        import redis.asyncio as aioredis
        from django.conf import settings
        from asgiref.sync import sync_to_async

        @sync_to_async
        def get_notification_payload(notif_id):
            import uuid
            notif_id = (notif_id or "").strip()
            if notif_id.startswith("{") and notif_id.endswith("}"):
                try:
                    import json
                    parsed = json.loads(notif_id)
                    if isinstance(parsed, dict) and "id" in parsed:
                        notif_id = parsed["id"]
                except Exception:
                    pass

            try:
                uuid.UUID(notif_id)
            except ValueError:
                return None

            from django.utils import timezone
            from apps.leads.models import Lead
            from .models import Notification
            n = Notification.objects.filter(id=notif_id).select_related("notification_type").first()
            if not n:
                return None
            lead_name = ""
            lead_phone = ""
            if n.related_type == "Lead" and n.related_id:
                lead = Lead.objects.filter(pk=n.related_id).first()
                if lead:
                    lead_name = lead.name
                    lead_phone = lead.phone

            return {
                "id": str(n.id),
                "title": n.title,
                "body": n.body,
                "type": n.notification_type.name if n.notification_type else "",
                "code": n.notification_type.code if n.notification_type else "",
                "priority": n.priority,
                "related_type": n.related_type,
                "related_id": n.related_id,
                "lead_name": lead_name,
                "lead_phone": lead_phone,
                "created_at": timezone.localtime(n.created_at).isoformat(),
                "is_read": n.is_read,
            }

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        channel = f"sse_notif:{user.id}"
        await pubsub.subscribe(channel)

        queue: asyncio.Queue = asyncio.Queue()

        async def _listen():
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        await queue.put(message["data"])
            except Exception:
                pass

        task = asyncio.create_task(_listen())
        try:
            while True:
                try:
                    notif_id = await asyncio.wait_for(queue.get(), timeout=25)
                    payload = await get_notification_payload(notif_id)
                    if payload:
                        yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            task.cancel()
            try:
                await pubsub.unsubscribe(channel)
                await r.aclose()
            except Exception:
                pass

    @staticmethod
    def mark_read(*, notification: Notification) -> None:
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read", "updated_at"])

    @staticmethod
    def delete(*, notification: Notification) -> None:
        notification.delete()

    @staticmethod
    def mark_all_read(*, recipient) -> int:
        return Notification.objects.filter(
            recipient=recipient, is_read=False
        ).update(is_read=True)

    @staticmethod
    def get_api_list(user) -> dict:
        from django.utils import timezone
        from apps.leads.models import Lead

        qs = Notification.objects.filter(
            recipient=user
        ).select_related("notification_type").order_by("-created_at")

        lead_ids = [n.related_id for n in qs if n.related_type == "Lead" and n.related_id]
        leads_map = {}
        if lead_ids:
            leads_map = {str(l.id): l for l in Lead.objects.filter(id__in=lead_ids)}

        items = []
        for n in qs:
            lead_name = ""
            lead_phone = ""
            if n.related_type == "Lead" and n.related_id:
                lead = leads_map.get(n.related_id)
                if not lead:
                    lead = Lead.objects.filter(pk=n.related_id).first()
                if lead:
                    lead_name = lead.name
                    lead_phone = lead.phone

            items.append({
                "id": str(n.id),
                "title": n.title,
                "body": n.body,
                "type": n.notification_type.name if n.notification_type else "",
                "code": n.notification_type.code if n.notification_type else "",
                "priority": n.priority,
                "related_type": n.related_type,
                "related_id": n.related_id,
                "lead_name": lead_name,
                "lead_phone": lead_phone,
                "created_at": timezone.localtime(n.created_at).isoformat(),
                "is_read": n.is_read,
            })

        unread = sum(1 for item in items if not item["is_read"])
        return {"items": items, "unread": unread}

