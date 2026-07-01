from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.companies.models import Company
from apps.core.exceptions import ValidationError
from apps.leads.constants import ActiveStatus, Origin, StageCode
from apps.leads.models import Lead, LeadSourceDefinition, LeadStageDefinition, SLAInstance, SLABreachEvent
from apps.distribution.services import SLAExpiryService
from apps.leads.services.duplicate_service import DuplicateService
from apps.leads.services.lead_creation_service import LeadCreationService
from apps.leads.services.sla_service import SLAService
from apps.policies.constants import PolicyCode
from apps.policies.models import CompanyPolicyValue, PolicyDefinition


class LeadServiceExtraTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="leads-extra-acme")
        self.source = LeadSourceDefinition.objects.create(code="CALL_CENTER", name="Call Center")
        self.broker_source = LeadSourceDefinition.objects.create(
            code="BROKER", name="Broker", requires_broker=True
        )
        self.stage = LeadStageDefinition.objects.create(code=StageCode.FRESH, name="Fresh")

    def test_validate_source_requires_configured_broker(self):
        with self.assertRaises(ValidationError):
            LeadCreationService._validate_source(
                self.broker_source,
                broker_owner=None,
                campaign=None,
                assigned_salesman=None,
            )

    def test_duplicate_service_marks_active_in_sla_duplicate_as_manual_case(self):
        Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="Existing",
            phone="123",
            active_status=ActiveStatus.ACTIVE,
            sla_deadline=timezone.now() + timezone.timedelta(hours=1),
        )

        result = DuplicateService.check(company=self.company, phone="123")

        self.assertTrue(result.is_duplicate)
        self.assertTrue(result.requires_manual)

    def test_origin_sla_uses_direct_and_broker_policy_values(self):
        direct_policy = PolicyDefinition.objects.create(
            code=PolicyCode.DIRECT_SLA,
            name="Direct SLA",
            module="leads",
            value_type="DURATION",
        )
        broker_policy = PolicyDefinition.objects.create(
            code=PolicyCode.BROKER_SLA,
            name="Broker SLA",
            module="leads",
            value_type="DURATION",
        )
        CompanyPolicyValue.objects.create(
            company=self.company,
            policy=direct_policy,
            value_json={"hours": 2},
        )
        CompanyPolicyValue.objects.create(
            company=self.company,
            policy=broker_policy,
            value_json={"hours": 4},
        )

        self.assertEqual(SLAService.origin_duration(self.company, Origin.DIRECT).total_seconds(), 7200)
        self.assertEqual(SLAService.origin_duration(self.company, Origin.BROKER).total_seconds(), 14400)

    def test_not_interested_stage_has_no_sla_duration(self):
        self.assertIsNone(SLAService.stage_duration(self.company, StageCode.NOT_INTERESTED))

    def test_broker_sla_expiry_forces_manual_even_when_policy_is_by_turn(self):
        expiry_policy = PolicyDefinition.objects.create(
            code=PolicyCode.SLA_EXPIRY_METHOD,
            name="SLA expiry method",
            module="leads",
            value_type="CODE",
        )
        CompanyPolicyValue.objects.create(
            company=self.company,
            policy=expiry_policy,
            value_json={"code": "BY_TURN"},
        )
        lead = Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="Broker SLA",
            phone="555",
            origin=Origin.BROKER,
        )
        sla = SLAInstance.objects.create(
            lead=lead,
            stage=self.stage,
            start_at=timezone.now(),
            deadline_at=timezone.now(),
        )

        with patch("apps.distribution.services.DistributionEngine.distribute") as distribute, \
                patch("apps.distribution.services.ManualDistributionEscalation.notify") as notify:
            processed = SLAExpiryService.process_instance(sla, task_id="broker-by-turn")

        self.assertTrue(processed)
        distribute.assert_not_called()
        notify.assert_called_once()
        self.assertEqual(
            SLABreachEvent.objects.get(sla_instance=sla).action_taken,
            "MANUAL",
        )
