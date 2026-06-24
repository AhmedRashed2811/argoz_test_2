"""Integration setup (docs §13.2 steps 1-4). Creates a per-company endpoint with
a generated secret and returns the copyable URL for Make/Zapier."""
from __future__ import annotations

import secrets

from django.conf import settings

from .models import IntegrationProvider, WebhookEndpoint


class IntegrationSetupService:
    @staticmethod
    def create_endpoint(*, company, provider_code: str, name: str, actor=None,
                        default_source_code="CAMPAIGN", default_campaign=None):
        provider, _ = IntegrationProvider.objects.get_or_create(
            code=provider_code, defaults={"name": provider_code.title()}
        )
        endpoint = WebhookEndpoint.objects.create(
            company=company, provider=provider, name=name,
            secret_token=secrets.token_urlsafe(32), created_by=actor,
            default_source_code=default_source_code, default_campaign=default_campaign,
        )
        return endpoint

    @staticmethod
    def endpoint_url(endpoint: WebhookEndpoint) -> str:
        base = settings.WEBHOOK_BASE_URL.rstrip("/")
        return f"{base}/integrations/webhooks/{endpoint.endpoint_uuid}/"
