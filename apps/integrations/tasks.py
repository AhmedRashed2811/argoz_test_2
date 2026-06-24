"""Webhook processing Celery tasks (docs §12.1). Tasks call services only."""
from __future__ import annotations

from celery import shared_task
from django.utils import timezone


@shared_task
def process_webhook_event(event_id: str):
    """Dedupe-safe import of a received webhook event (docs §13.2)."""
    from .services import WebhookLeadImportService

    event = WebhookLeadImportService.process(event_id=event_id)
    return event.status


@shared_task
def retry_failed_webhooks(max_attempts: int = 5, batch_size: int = 50):
    """Beat every 5-15 min: retry failed events with attempt cap (docs §12.1)."""
    from .models import WebhookEvent, WebhookRetry
    from .services import WebhookLeadImportService

    failed = WebhookEvent.objects.filter(status="FAILED")[:batch_size]
    retried = 0
    for event in failed:
        attempts = event.retries.count()
        if attempts >= max_attempts:
            continue
        retry = WebhookRetry.objects.create(
            webhook_event=event, attempt_number=attempts + 1,
            scheduled_at=timezone.now(),
        )
        result = WebhookLeadImportService.process(event_id=event.id)
        retry.status = result.status
        retry.processed_at = timezone.now()
        retry.error = result.error
        retry.save(update_fields=["status", "processed_at", "error"])
        retried += 1
    return retried
