from django.test import TestCase

from apps.audit.models import AuditEventField, AuditLog
from apps.audit.services import AuditService, DiffService
from apps.companies.models import Company
from apps.core.constants import AuditAction


class AuditServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="audit-acme")

    def test_diff_service_reports_changed_fields_only(self):
        self.assertEqual(
            DiffService.diff({"name": "Old", "phone": "1"}, {"name": "New", "phone": "1"}),
            {"name": {"old": "Old", "new": "New"}},
        )

    def test_log_stores_changed_fields_and_field_rows(self):
        log = AuditService.log(
            action=AuditAction.UPDATE,
            company=self.company,
            module="accounts",
            entity_type="User",
            entity_id="1",
            before={"email": "old@example.com"},
            after={"email": "new@example.com"},
            request_meta={"ip": "127.0.0.1"},
        )

        self.assertEqual(log.changed_fields["email"]["old"], "old@example.com")
        self.assertEqual(log.request_meta, {"ip": "127.0.0.1"})
        self.assertEqual(AuditEventField.objects.filter(audit=log).count(), 1)

    def test_payload_filters_permission_audit_entities(self):
        AuditLog.objects.create(
            company=self.company,
            action=AuditAction.PERMISSION_CHANGE,
            entity_type="UserPermissionOverride",
            entity_id="1",
        )
        AuditLog.objects.create(
            company=self.company,
            action=AuditAction.UPDATE,
            entity_type="Lead",
            entity_id="1",
        )

        payload = AuditService.get_audit_logs_payload(
            company=self.company,
            filters={},
            is_permission_audit=True,
        )

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["logs"][0]["entity_type"], "UserPermissionOverride")
