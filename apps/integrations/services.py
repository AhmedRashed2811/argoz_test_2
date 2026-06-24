"""Webhook receive → normalize → import (docs §13). Store + audit before
processing, dedupe, map required name/phone, then call LeadCreationService so
webhook leads pass the same source/attribution/distribution/audit path as
manual leads. Processing is idempotent and retryable."""
from __future__ import annotations

import hashlib
import json

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import AuditService
from apps.core.constants import AuditAction
from apps.core.exceptions import ValidationError

from .models import WebhookEndpoint, WebhookEvent


def _dedupe_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


class WebhookReceiverService:
    @staticmethod
    def authenticate(*, endpoint_uuid, token) -> WebhookEndpoint:
        endpoint = WebhookEndpoint.objects.filter(
            endpoint_uuid=endpoint_uuid, status="ACTIVE"
        ).first()
        if endpoint is None or not token or token != endpoint.secret_token:
            raise ValidationError("Invalid webhook endpoint or token.")
        return endpoint

    @staticmethod
    @transaction.atomic
    def receive(*, endpoint: WebhookEndpoint, payload: dict,
                external_event_id: str = "") -> WebhookEvent:
        """Persist + dedupe the event (docs §13.2). Returns the existing event
        when a duplicate is detected so callers stay idempotent."""
        dedupe = _dedupe_hash(payload)
        try:
            with transaction.atomic():
                event = WebhookEvent.objects.create(
                    endpoint=endpoint, payload=payload,
                    external_event_id=external_event_id or "", dedupe_hash=dedupe,
                )
        except IntegrityError:
            existing = WebhookEvent.objects.filter(
                endpoint=endpoint
            ).filter(
                models_dedupe_or_event(external_event_id, dedupe)
            ).first()
            return existing
        endpoint.last_used_at = timezone.now()
        endpoint.save(update_fields=["last_used_at", "updated_at"])
        AuditService.log(
            action=AuditAction.WEBHOOK_EVENT, instance=event, company=endpoint.company,
            module="integrations", after={"status": "RECEIVED"}, source="webhook",
        )
        return event


class MappingService:
    @staticmethod
    def normalize(*, endpoint: WebhookEndpoint, payload: dict) -> dict:
        """Apply field mappings; enforce required name + phone (docs §13.2)."""
        mappings = list(endpoint.mappings.all())
        result: dict = {}
        if not mappings:
            # Sensible default mapping for Make/Zapier Meta lead payloads.
            result = {
                "name": payload.get("name") or payload.get("full_name", ""),
                "phone": payload.get("phone") or payload.get("phone_number", ""),
                "email": payload.get("email", ""),
            }
        else:
            for m in mappings:
                value = payload.get(m.source_field)
                if m.required and not value:
                    raise ValidationError(f"Missing required field: {m.source_field}")
                result[m.target_field] = value
        if not result.get("name") or not result.get("phone"):
            raise ValidationError("Webhook lead requires name and phone (docs §13.2).")
        return result


class WebhookLeadImportService:
    @staticmethod
    @transaction.atomic
    def process(*, event_id) -> WebhookEvent:
        from apps.leads.services import LeadCreationService

        event = WebhookEvent.objects.select_for_update().select_related(
            "endpoint", "endpoint__company"
        ).get(id=event_id)
        # Idempotency: never reprocess a done event (docs §12.2).
        if event.status == "PROCESSED":
            return event
        endpoint = event.endpoint
        try:
            fields = MappingService.normalize(endpoint=endpoint, payload=event.payload)
            lead = LeadCreationService.create(
                company=endpoint.company,
                source_code=endpoint.default_source_code,
                name=fields["name"], phone=fields["phone"],
                email=fields.get("email", ""),
                campaign=endpoint.default_campaign,
                auto_distribute=True,
                metadata={"webhook_event": str(event.id)},
            )
            event.created_lead = lead
            event.status = "PROCESSED"
            event.processed_at = timezone.now()
            event.error = ""
        except Exception as exc:  # noqa: BLE001
            event.status = "FAILED"
            event.error = str(exc)[:1000]
            _notify_webhook_failure(endpoint, event)
        event.save(update_fields=["created_lead", "status", "processed_at", "error"])
        return event


def _notify_webhook_failure(endpoint, event):
    from apps.notifications.constants import NotificationCode
    from apps.notifications.services import NotificationService

    from apps.accounts.models import User
    from apps.authorization.services import EffectivePermissionResolver

    admins = [
        u for u in User.objects.filter(is_active=True, profile__company=endpoint.company)
        if EffectivePermissionResolver.has(u, "integrations.webhooks.manage")
    ]
    NotificationService.create_for_users(
        company=endpoint.company, recipients=admins,
        code=NotificationCode.WEBHOOK_FAILED, title="Webhook processing failed",
        related_type="WebhookEvent", related_id=event.pk,
    )


def models_dedupe_or_event(external_event_id, dedupe):
    from django.db.models import Q

    q = Q(dedupe_hash=dedupe)
    if external_event_id:
        q |= Q(external_event_id=external_event_id)
    return q
