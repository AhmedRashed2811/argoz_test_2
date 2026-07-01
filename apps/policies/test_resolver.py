from django.test import TestCase

from apps.companies.models import Company
from apps.core.exceptions import PolicyError
from apps.policies.constants import PolicyCode, ValueType
from apps.policies.models import (
    CompanyPolicyValue,
    PolicyDefinition,
    PolicyOptionDefinition,
    PolicyParameter,
)
from apps.policies.services import PolicyManagementService, PolicyResolver


class PolicyResolverTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="policy-acme")
        self.option_policy = PolicyDefinition.objects.create(
            code=PolicyCode.DEFAULT_AUTO_DISTRIBUTION_METHOD,
            name="Distribution method",
            module="leads",
            value_type=ValueType.OPTION,
        )
        self.round_robin = PolicyOptionDefinition.objects.create(
            policy=self.option_policy,
            code="ROUND_ROBIN",
            label="Round Robin",
            strategy_code="ROUND_ROBIN",
        )
        self.duration_policy = PolicyDefinition.objects.create(
            code=PolicyCode.DIRECT_SLA,
            name="Direct SLA",
            module="leads",
            value_type=ValueType.DURATION,
        )

    def test_option_and_strategy_resolve_from_selected_option(self):
        CompanyPolicyValue.objects.create(
            company=self.company,
            policy=self.option_policy,
            selected_option=self.round_robin,
        )

        self.assertEqual(
            PolicyResolver.option_code(self.company, PolicyCode.DEFAULT_AUTO_DISTRIBUTION_METHOD),
            "ROUND_ROBIN",
        )
        self.assertEqual(
            PolicyResolver.strategy_code(self.company, PolicyCode.DEFAULT_AUTO_DISTRIBUTION_METHOD),
            "ROUND_ROBIN",
        )

    def test_value_json_and_parameters_resolve_with_defaults(self):
        company_value = CompanyPolicyValue.objects.create(
            company=self.company,
            policy=self.duration_policy,
            value_json={"hours": 2},
        )
        PolicyParameter.objects.create(
            company_policy=company_value,
            key="warning",
            value_json={"minutes_before": 15},
        )

        self.assertEqual(PolicyResolver.value(self.company, PolicyCode.DIRECT_SLA), {"hours": 2})
        self.assertEqual(
            PolicyResolver.param(self.company, PolicyCode.DIRECT_SLA, "warning"),
            {"minutes_before": 15},
        )
        self.assertEqual(
            PolicyResolver.value(self.company, "missing.policy", default="fallback"),
            "fallback",
        )

    def test_require_value_raises_when_policy_is_not_configured(self):
        with self.assertRaises(PolicyError):
            PolicyResolver.require_value(self.company, "missing.policy")


class PolicyManagementServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="policy-edit-acme")

    def test_set_duration_from_post_stores_structured_value(self):
        policy = PolicyDefinition.objects.create(
            code=PolicyCode.BROKER_SLA,
            name="Broker SLA",
            module="leads",
            value_type=ValueType.DURATION,
        )

        summary = PolicyManagementService.set_value_from_post(
            company=self.company,
            policy=policy,
            post_data={"days": "1", "hours": "2", "minutes": "30"},
        )

        value = CompanyPolicyValue.objects.get(company=self.company, policy=policy)
        self.assertEqual(value.value_json, {"days": 1, "hours": 2, "minutes": 30})
        self.assertEqual(summary["current_display"], "1d 2h 30m")

    def test_set_boolean_from_post_stores_false_when_not_true(self):
        policy = PolicyDefinition.objects.create(
            code=PolicyCode.SALES_VIEW_INACTIVE,
            name="Sales view inactive",
            module="leads",
            value_type=ValueType.BOOLEAN,
        )

        PolicyManagementService.set_value_from_post(
            company=self.company,
            policy=policy,
            post_data={"bool_value": "false"},
        )

        value = CompanyPolicyValue.objects.get(company=self.company, policy=policy)
        self.assertFalse(value.value_json)
