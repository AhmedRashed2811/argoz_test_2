"""Notification + email Celery tasks (docs §12.1). Tasks call services and the
channel layer; no business logic here."""
from __future__ import annotations

from celery import shared_task
from django.utils import timezone


@shared_task
def fanout_notification(notification_id: str):
    """Push a created notification to the recipient's WebSocket group (§12.1)."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from .models import Notification, NotificationDelivery
    from .constants import Channel

    import json
    import redis as sync_redis
    from django.conf import settings

    notif = Notification.objects.filter(id=notification_id).select_related(
        "recipient", "notification_type"
    ).first()
    if notif is None:
        return

    lead_name = ""
    lead_phone = ""
    if notif.related_type == "Lead" and notif.related_id:
        from apps.leads.models import Lead
        lead = Lead.objects.filter(pk=notif.related_id).first()
        if lead:
            lead_name = lead.name
            lead_phone = lead.phone

    payload = {
        "id": str(notif.id),
        "title": notif.title,
        "body": notif.body,
        "code": notif.notification_type.code,
        "type": notif.notification_type.name,
        "priority": notif.priority,
        "related_type": notif.related_type,
        "related_id": notif.related_id,
        "lead_name": lead_name,
        "lead_phone": lead_phone,
        "created_at": notif.created_at.isoformat(),
    }

    # WebSocket delivery via Django Channels layer.
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(
            f"notifications_{notif.recipient_id}",
            {"type": "notify", "payload": payload},
        )

    # SSE delivery via direct Redis pub/sub (more reliable cross-process).
    r = sync_redis.from_url(settings.REDIS_URL)
    r.publish(f"sse_notif:{notif.recipient_id}", str(notif.id))
    r.close()
    NotificationDelivery.objects.filter(
        notification=notif, channel=Channel.WEBSOCKET
    ).update(status="SENT", sent_at=timezone.now())

    # Queue email copies where the delivery policy added an EMAIL channel.
    if NotificationDelivery.objects.filter(
        notification=notif, channel=Channel.EMAIL
    ).exists():
        _queue_email(notif)


def _queue_email(notif):
    from .models import EmailOutbox

    if not notif.recipient.email:
        return
    EmailOutbox.objects.create(
        company=notif.company, to_email=notif.recipient.email,
        subject=notif.title, body=notif.body,
    )


@shared_task
def send_email_outbox(batch_size: int = 50):
    """Send pending outbox emails with attempt tracking (docs §12.1, outbox)."""
    from django.conf import settings
    from django.core.mail import send_mail

    from .models import EmailOutbox

    now = timezone.now()
    pending = EmailOutbox.objects.filter(status="PENDING").filter(
        models_send_after_ready(now)
    )[:batch_size]
    sent = 0
    for email in pending:
        try:
            send_mail(email.subject, email.body, settings.DEFAULT_FROM_EMAIL,
                      [email.to_email])
            email.status = "SENT"
            sent += 1
        except Exception as exc:  # noqa: BLE001
            email.status = "FAILED"
            email.last_error = str(exc)[:500]
        email.attempts += 1
        email.save(update_fields=["status", "last_error", "attempts", "updated_at"])
    return sent


def models_send_after_ready(now):
    from django.db.models import Q

    return Q(send_after__isnull=True) | Q(send_after__lte=now)
