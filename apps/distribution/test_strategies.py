from types import SimpleNamespace

from django.test import TestCase

from apps.accounts.models import Language, Team, TeamMember, User, UserLanguage, UserProfile
from apps.companies.models import Company
from apps.distribution.models import RotationPointer
from apps.distribution.selectors import eligible_pool
from apps.distribution.strategies.by_turn import ByTurnStrategy
from apps.distribution.strategies.round_robin import RoundRobinStrategy
from apps.leads.constants import ActiveStatus, ScopeMode
from apps.leads.models import Lead, LeadSourceDefinition, LeadStageDefinition


class DistributionStrategyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="distribution-acme")
        self.language = Language.objects.create(code="ar", name="Arabic")
        self.source = LeadSourceDefinition.objects.create(code="CALL_CENTER", name="Call Center")
        self.stage = LeadStageDefinition.objects.create(code="FRESH", name="Fresh")
        self.team = Team.objects.create(company=self.company, name="Team")
        self.user_one = User.objects.create_user(email="one@example.com")
        self.user_two = User.objects.create_user(email="two@example.com")
        for user in (self.user_one, self.user_two):
            UserProfile.objects.create(user=user, company=self.company)
            UserLanguage.objects.create(user=user, language=self.language)
            TeamMember.objects.create(team=self.team, user=user)

    def test_eligible_pool_filters_by_language(self):
        english = Language.objects.create(code="en", name="English")

        self.assertEqual(
            [member.user for member in eligible_pool(company=self.company, language=english)],
            [],
        )
        self.assertEqual(
            set(member.user for member in eligible_pool(company=self.company, language=self.language)),
            {self.user_one, self.user_two},
        )

    def test_round_robin_selects_candidate_with_fewest_active_leads(self):
        Lead.objects.create(
            company=self.company,
            source=self.source,
            current_stage=self.stage,
            name="Busy lead",
            phone="1",
            assigned_salesman=self.user_one,
            active_status=ActiveStatus.ACTIVE,
        )
        pool = eligible_pool(company=self.company, language=self.language)

        decision = RoundRobinStrategy().select_candidate(
            company=self.company,
            lead=SimpleNamespace(),
            eligible_pool=pool,
            context=SimpleNamespace(),
        )

        self.assertEqual(decision.salesman, self.user_two)

    def test_by_turn_advances_pointer_with_language_scope(self):
        pool = eligible_pool(company=self.company, language=self.language)
        context = SimpleNamespace(
            language=self.language,
            scope_mode=ScopeMode.ALL_SALESMEN,
            params={},
        )

        first = ByTurnStrategy().select_candidate(
            company=self.company,
            lead=SimpleNamespace(),
            eligible_pool=pool,
            context=context,
        )
        second = ByTurnStrategy().select_candidate(
            company=self.company,
            lead=SimpleNamespace(),
            eligible_pool=pool,
            context=context,
        )

        self.assertNotEqual(first.salesman, second.salesman)
        pointer = RotationPointer.objects.get(
            company=self.company,
            pointer_code="BY_TURN",
            scope=f"{ScopeMode.ALL_SALESMEN}:ar",
        )
        self.assertEqual(pointer.current_index, 0)
