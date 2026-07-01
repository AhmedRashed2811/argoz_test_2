from django.test import TestCase

from apps.companies.models import Company
from apps.core.exceptions import ValidationError
from apps.integrations.models import (
    IntegrationProvider,
    WebhookEndpoint,
    WebhookEvent,
    WebhookMapping,
)
from apps.integrations.services import MappingService, WebhookReceiverService, _dedupe_hash


class IntegrationServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="integrations-acme")
        self.provider = IntegrationProvider.objects.create(code="MAKE", name="Make")
        self.endpoint = WebhookEndpoint.objects.create(
            company=self.company,
            provider=self.provider,
            name="Meta leads",
            secret_token="secret",
        )

    def test_authenticate_accepts_active_endpoint_with_matching_token(self):
        endpoint = WebhookReceiverService.authenticate(
            endpoint_uuid=self.endpoint.endpoint_uuid,
            token="secret",
        )

        self.assertEqual(endpoint, self.endpoint)

    def test_authenticate_rejects_wrong_token(self):
        with self.assertRaises(ValidationError):
            WebhookReceiverService.authenticate(
                endpoint_uuid=self.endpoint.endpoint_uuid,
                token="wrong",
            )

    def test_receive_is_idempotent_by_external_event_id(self):
        first = WebhookReceiverService.receive(
            endpoint=self.endpoint,
            payload={"name": "Jane", "phone": "123"},
            external_event_id="evt-1",
        )
        second = WebhookReceiverService.receive(
            endpoint=self.endpoint,
            payload={"name": "Different", "phone": "999"},
            external_event_id="evt-1",
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(WebhookEvent.objects.count(), 1)

    def test_receive_is_idempotent_by_payload_hash(self):
        first = WebhookReceiverService.receive(
            endpoint=self.endpoint,
            payload={"phone": "123", "name": "Jane"},
        )
        second = WebhookReceiverService.receive(
            endpoint=self.endpoint,
            payload={"name": "Jane", "phone": "123"},
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.dedupe_hash, _dedupe_hash(second.payload))

    def test_default_mapping_requires_name_and_phone(self):
        with self.assertRaises(ValidationError):
            MappingService.normalize(endpoint=self.endpoint, payload={"name": "Jane"})

    def test_custom_mapping_enforces_required_fields(self):
        WebhookMapping.objects.create(
            endpoint=self.endpoint,
            source_field="lead_name",
            target_field="name",
            required=True,
        )
        WebhookMapping.objects.create(
            endpoint=self.endpoint,
            source_field="mobile",
            target_field="phone",
            required=True,
        )

        normalized = MappingService.normalize(
            endpoint=self.endpoint,
            payload={"lead_name": "Jane", "mobile": "123"},
        )

        self.assertEqual(normalized, {"name": "Jane", "phone": "123"})
