"""Bootstrap the configurable data the engine depends on (docs §19 Phase 1-2:
seed stages, sources, policies, default groups, strategies, notification types).
Idempotent — safe to re-run. This is configuration data, not business records."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.companies.models import Company
from apps.leads.constants import (
    Origin,
    ScopeMode,
    SLAExpiryMethod,
    SourceCode,
    StageCode,
)
from apps.leads.models import (
    HowDidYouKnowOption,
    LeadSourceDefinition,
    LeadStageDefinition,
)
from apps.marketing.models import SocialPlatformDefinition, StreetAdTypeDefinition
from apps.notifications.constants import Channel
from apps.notifications.models import NotificationType
from apps.policies.constants import PolicyCode, ValueType
from apps.policies.models import (
    CompanyPolicyValue,
    PolicyDefinition,
    PolicyOptionDefinition,
    StrategyDefinition,
)

# (code, name, is_active_stage, is_terminal, allows_reminder, resets_on_rotation)
STAGES = [
    (StageCode.FRESH, "Fresh", True, False, True, True),
    (StageCode.INTERESTED, "Interested", True, False, True, True),
    (StageCode.NOT_INTERESTED, "Not Interested", False, True, False, False),
    (StageCode.FOLLOW_UP, "Follow-up", True, False, True, True),
    (StageCode.MEETING, "Meeting", True, False, True, True),
    (StageCode.NOT_REACHED, "Not Reached", True, False, True, True),
    (StageCode.FROZEN, "Frozen", True, False, True, True),
]

# (code, name, req_campaign, req_broker, req_referrer, req_salesman)
SOURCES = [
    (SourceCode.SELF_GENERATED, "Self-Generated", False, False, False, False),
    (SourceCode.CAMPAIGN, "Campaign", True, False, False, False),
    (SourceCode.BROKER, "Broker", False, True, False, False),
    (SourceCode.WALK_IN, "Walk-in", False, False, False, False),
    (SourceCode.CALL_CENTER, "Call Center", False, False, False, False),
    (SourceCode.EXHIBITION, "Exhibition", False, False, False, True),
    (SourceCode.REFERRAL, "Referral", False, False, True, False),
    (SourceCode.EXISTING_CLIENT, "Existing Client", False, False, False, False),
]

STRATEGIES = [
    ("ROUND_ROBIN", "Round Robin",
     "apps.distribution.strategies.round_robin.RoundRobinStrategy"),
    ("BY_TURN", "By Turn",
     "apps.distribution.strategies.by_turn.ByTurnStrategy"),
]

STREET_AD_TYPES = [
    ("BILLBOARD", "Billboard", True), ("BANNER", "Banner", False),
    ("BUS_SHELTER", "Bus Shelter", True), ("LED_SCREEN", "LED Screen", True),
    ("TRANSIT_WRAP", "Transit/Bus Wrap", False), ("WALL_MURAL", "Wall Mural", True),
    ("LAMP_POST", "Lamp Post", True), ("BRIDGE_BANNER", "Bridge Banner", True),
    ("OTHERS", "Others", False),
]

SOCIAL_PLATFORMS = [
    ("META", "Meta", True), ("WHATSAPP", "WhatsApp", True), ("TIKTOK", "TikTok", False),
    ("LINKEDIN", "LinkedIn", False), ("X", "X", False),
    ("GOOGLE_ADS", "Google Ads/Website", True),
]

# Default groups (docs §5.2). Permissions are seeded lazily as referenced; here
# we create the role templates so admins can fill them from the UI.
DEFAULT_GROUPS = [
    ("SYSTEM_ADMINS", "System Admins"),
    ("SALES", "Sales"),
    ("SALES_HEAD", "Sales Head"),
    ("SALES_OPERATION", "Sales Operation"),
    ("DIRECTORS", "Directors"),
    ("CALL_CENTER", "Call Center"),
    ("FINANCE_MANAGERS", "Finance Managers"),
    ("RECEPTIONISTS", "Receptionists"),
    ("BROKERS", "Brokers"),
    ("MARKETING_MEMBERS", "Marketing Members"),
    ("MARKETING_MANAGERS", "Marketing Managers"),
]


class Command(BaseCommand):
    help = "Seed configurable CRM data (stages, sources, policies, roles, types)."

    @transaction.atomic
    def handle(self, *args, **options):
        company = self._company()
        self._stages()
        self._sources()
        self._how_did_you_know()
        self._strategies()
        self._street_types()
        self._social_platforms()
        self._notification_types()
        self._policies(company)
        self._groups(company)
        self._pages()
        self._permissions()
        self._role_defaults(company)
        self.stdout.write(self.style.SUCCESS("CRM seed complete."))

    def _company(self) -> Company:
        company, created = Company.objects.get_or_create(
            slug="argoz", defaults={"name": "Argoz Real Estate"}
        )
        self._say("Company", created)
        return company

    def _stages(self):
        for code, name, active, terminal, reminder, reset in STAGES:
            LeadStageDefinition.objects.update_or_create(
                code=code, defaults=dict(
                    name=name, is_active_stage=active, is_terminal=terminal,
                    allows_reminder=reminder, resets_on_rotation=reset,
                ),
            )
        self.stdout.write(f"  stages: {len(STAGES)}")

    def _sources(self):
        for code, name, camp, broker, ref, sales in SOURCES:
            LeadSourceDefinition.objects.update_or_create(
                code=code, defaults=dict(
                    name=name, requires_campaign=camp, requires_broker=broker,
                    requires_referrer=ref, requires_salesman=sales,
                ),
            )
        self.stdout.write(f"  sources: {len(SOURCES)}")

    def _how_did_you_know(self):
        # 'Website' must always be present (leads spec §4.3).
        options = [
            ("WEBSITE", "Website", 0), ("FRIEND", "Friend / Referral", 1),
            ("SOCIAL_MEDIA", "Social Media", 2), ("PASSING_BY", "Passing By", 3),
            ("EXHIBITION", "Exhibition", 4), ("AD", "Advertisement", 5),
        ]
        for code, name, order in options:
            HowDidYouKnowOption.objects.update_or_create(
                code=code, defaults=dict(name=name, order_index=order),
            )
        self.stdout.write(f"  how-did-you-know: {len(options)} (Website included)")

    def _strategies(self):
        for code, name, path in STRATEGIES:
            StrategyDefinition.objects.update_or_create(
                code=code, defaults=dict(name=name, class_path=path, module="distribution"),
            )
        self.stdout.write(f"  strategies: {len(STRATEGIES)}")

    def _street_types(self):
        for code, name, loc in STREET_AD_TYPES:
            StreetAdTypeDefinition.objects.update_or_create(
                code=code, defaults=dict(name=name, requires_exact_location=loc),
            )

    def _social_platforms(self):
        for code, name, webhook in SOCIAL_PLATFORMS:
            SocialPlatformDefinition.objects.update_or_create(
                code=code, defaults=dict(name=name, supports_webhook=webhook),
            )

    def _notification_types(self):
        from apps.notifications.constants import NotificationCode

        codes = [v for k, v in vars(NotificationCode).items() if not k.startswith("_")]
        for code in codes:
            NotificationType.objects.get_or_create(
                code=code,
                defaults=dict(name=code.replace("_", " ").title(),
                              default_channels=[Channel.IN_APP, Channel.WEBSOCKET]),
            )
        self.stdout.write(f"  notification types: {len(codes)}")

    def _policies(self, company):
        # (code, name, module, value_type, [(option_code, label, strategy_code)])
        defs = [
            (PolicyCode.DIRECT_SLA, "Direct Lead SLA", "leads", ValueType.DURATION, []),
            (PolicyCode.BROKER_SLA, "Broker Lead SLA", "leads", ValueType.DURATION, []),
            (PolicyCode.SLA_EXPIRY_METHOD, "SLA Expiry Method", "leads", ValueType.OPTION,
             [(SLAExpiryMethod.ROUND_ROBIN, "Round Robin", "ROUND_ROBIN"),
              (SLAExpiryMethod.RETRY_TEAM_ESCALATION, "Retry + Team Escalation", ""),
              (SLAExpiryMethod.MANUAL, "Manual", "")]),
            (PolicyCode.DEFAULT_AUTO_DISTRIBUTION_METHOD, "Auto Distribution Method",
             "leads", ValueType.OPTION,
             [("ROUND_ROBIN", "Round Robin", "ROUND_ROBIN"),
              ("BY_TURN", "By Turn", "BY_TURN")]),
            (PolicyCode.DISTRIBUTION_SCOPE_MODE, "Distribution Scope Mode", "leads",
             ValueType.OPTION,
             [(ScopeMode.TEAM_THEN_SALESMAN, "Team then Salesman", ""),
              (ScopeMode.TEAM_HEAD_DECIDES, "Team, Head Decides", ""),
              (ScopeMode.ALL_SALESMEN, "All Salesmen", "")]),
            (PolicyCode.RETRY_ATTEMPTS_PER_TEAM, "Retry Attempts per Team", "leads",
             ValueType.INTEGER, []),
            (PolicyCode.BUDGET_CALCULATION_RULE, "Budget Calculation Rule", "marketing",
             ValueType.OPTION,
             [("INCLUDE_MAIN_AND_CHILD", "Main + Child", ""), ("CUSTOM", "Custom", "")]),
            (PolicyCode.LANGUAGE_DEFAULT, "Default Language", "leads", ValueType.CODE, []),
            (PolicyCode.SELF_GENERATED_SALESMAN_POLICY, "Self-Generated Salesman Policy",
             "leads", ValueType.OPTION,
             [("KEEP_WITH_OWNER", "Keep with owner", ""),
              ("REDISTRIBUTE_AFTER_SLA", "Redistribute after SLA", "")]),
            (PolicyCode.SELF_GENERATED_HEAD_ASSIGNMENT,
             "Self-Generated Head Assignment", "leads", ValueType.OPTION,
             [("SELF_OR_MANUAL_TEAM", "Self or manual team member", ""),
              ("AUTO_ROUND_ROBIN_TEAM", "Auto round-robin within team", "")]),
            (PolicyCode.BROKER_ALSO_ASSIGN_SALESMAN,
             "Broker Lead Also Assigned to Salesman", "leads", ValueType.BOOLEAN, []),
            (PolicyCode.WALKIN_RECEPTION_POLICY, "Walk-in Reception Policy", "leads",
             ValueType.OPTION,
             [("OPEN_FLOOR", "Open Floor", ""), ("TEAM_TURN", "Team Turn", ""),
              ("FULL_ROTATION", "Full Rotation", "")]),
            (PolicyCode.EXISTING_CLIENT_POLICY, "Existing Client Policy", "leads",
             ValueType.OPTION,
             [("PRESERVE_PRIOR_RELATIONSHIP", "Preserve prior relationship", ""),
              ("REDISTRIBUTE", "Redistribute", "")]),
            (PolicyCode.NOT_REACHED_REMINDER_MODE, "Not Reached Reminder Mode", "leads",
             ValueType.OPTION, [("AUTOMATIC", "Automatic", ""), ("MANUAL", "Manual", "")]),
            (PolicyCode.FRESH_REMINDER_SCHEDULE, "Fresh Reminder Schedule", "leads",
             ValueType.JSON, []),
            (PolicyCode.CAMPAIGN_TYPE_REPEATABILITY, "Campaign Type Repeatability",
             "marketing", ValueType.BOOLEAN, []),
            (PolicyCode.TYPE_DATE_POLICY, "Campaign Type Date Policy", "marketing",
             ValueType.OPTION,
             [("STRICT_WITHIN_CAMPAIGN", "Strict within campaign", ""),
              ("WARN_ONLY", "Warn only", "")]),
            (PolicyCode.FINANCE_REASON_REQUIRED, "Finance Reason Required", "marketing",
             ValueType.JSON, []),
            (PolicyCode.WEBHOOK_MAPPING_POLICY, "Webhook Mapping Policy", "integration",
             ValueType.JSON, []),
            (PolicyCode.NOTIFICATION_DELIVERY_POLICY, "Notification Delivery Policy",
             "notification", ValueType.JSON, []),
        ]
        # Per-stage SLA durations.
        for stage in (StageCode.FRESH, StageCode.INTERESTED, StageCode.FOLLOW_UP,
                      StageCode.MEETING, StageCode.NOT_REACHED, StageCode.FROZEN):
            defs.append((f"{PolicyCode.STAGE_SLA}.{stage.lower()}",
                         f"{stage} Stage SLA", "leads", ValueType.DURATION, []))

        for code, name, module, vtype, options in defs:
            policy, _ = PolicyDefinition.objects.update_or_create(
                code=code, defaults=dict(name=name, module=module, value_type=vtype),
            )
            for ocode, label, scode in options:
                PolicyOptionDefinition.objects.update_or_create(
                    policy=policy, code=ocode,
                    defaults=dict(label=label, strategy_code=scode),
                )

        # Sensible default selections + durations so the engine runs out of the box.
        self._select(company, PolicyCode.SLA_EXPIRY_METHOD, SLAExpiryMethod.ROUND_ROBIN)
        self._select(company, PolicyCode.DEFAULT_AUTO_DISTRIBUTION_METHOD, "ROUND_ROBIN")
        self._select(company, PolicyCode.DISTRIBUTION_SCOPE_MODE, ScopeMode.ALL_SALESMEN)
        self._select(company, PolicyCode.WALKIN_RECEPTION_POLICY, "OPEN_FLOOR")
        self._select(company, PolicyCode.EXISTING_CLIENT_POLICY,
                     "PRESERVE_PRIOR_RELATIONSHIP")
        self._set_value(company, PolicyCode.LANGUAGE_DEFAULT, {"code": "ar"})
        self._set_value(company, PolicyCode.DIRECT_SLA, {"hours": 2})
        self._set_value(company, PolicyCode.BROKER_SLA, {"hours": 4})
        self._set_value(company, f"{PolicyCode.STAGE_SLA}.fresh", {"hours": 2})
        self._select(company, PolicyCode.SELF_GENERATED_SALESMAN_POLICY, "KEEP_WITH_OWNER")
        self._select(company, PolicyCode.SELF_GENERATED_HEAD_ASSIGNMENT,
                     "SELF_OR_MANUAL_TEAM")
        self._set_value(company, PolicyCode.BROKER_ALSO_ASSIGN_SALESMAN, True)
        self.stdout.write(f"  policies: {len(defs)}")

    def _select(self, company, code, option_code):
        policy = PolicyDefinition.objects.get(code=code)
        option = policy.options.filter(code=option_code).first()
        CompanyPolicyValue.objects.update_or_create(
            company=company, policy=policy, defaults={"selected_option": option},
        )

    def _set_value(self, company, code, value_json):
        policy = PolicyDefinition.objects.get(code=code)
        CompanyPolicyValue.objects.update_or_create(
            company=company, policy=policy, defaults={"value_json": value_json},
        )

    def _groups(self, company):
        from apps.authorization.models import RoleGroup

        for code, name in DEFAULT_GROUPS:
            RoleGroup.objects.update_or_create(
                company=company, code=code,
                defaults=dict(name=name, is_system_default=True),
            )
        self.stdout.write(f"  role groups: {len(DEFAULT_GROUPS)}")

    def _pages(self):
        from apps.authorization.models import PageDefinition

        # (module, code, name, url_name, menu_order)
        pages = [
            ("dashboard", "main", "Dashboard", "dashboard:index", 0),
            ("leads", "dashboard", "Leads", "leads:list", 1),
            ("marketing", "campaigns", "Campaigns", "marketing:campaign_list", 2),
            ("finance", "dashboard", "Finance Approvals", "finance:campaign_approval", 3),
            ("notifications", "view_own", "Notifications", "notifications:list", 4),
            ("admin", "users", "Users", "accounts:user_list", 10),
            ("admin", "teams", "Sales Teams", "accounts:team_list", 11),
            ("authorization", "roles", "Roles & Permissions",
             "authorization:role_list", 11),
            ("policies", "company", "Policies", "policies:list", 12),
            ("audit", "view_all", "Audit Log", "audit:list", 13),
            ("integrations", "webhooks", "Webhooks", "integrations:webhook_list", 14),
        ]
        for module, code, name, url_name, order in pages:
            PageDefinition.objects.update_or_create(
                code=f"{module}.{code}",
                defaults=dict(module=module, name=name, url_name=url_name,
                              menu_order=order, is_menu_item=True),
            )
        self.stdout.write(f"  pages: {len(pages)}")

    def _permissions(self):
        from apps.authorization.models import PageDefinition, PermissionDefinition, RiskLevel

        # Every code referenced by view decorators / selectors (docs §5.1).
        codes = [
            ("dashboard.main.access", "Open dashboard", RiskLevel.LOW),
            ("admin.users.access", "Open users page", RiskLevel.MEDIUM),
            ("admin.users.create", "Create users", RiskLevel.MEDIUM),
            ("admin.users.update", "Update users", RiskLevel.MEDIUM),
            ("admin.users.delete", "Delete users", RiskLevel.HIGH),
            ("admin.teams.access", "Open sales teams page", RiskLevel.LOW),
            ("admin.teams.create", "Create sales teams", RiskLevel.MEDIUM),
            ("admin.teams.update", "Update sales teams", RiskLevel.MEDIUM),
            ("admin.teams.delete", "Deactivate sales teams", RiskLevel.HIGH),
            ("leads.dashboard.access", "Open leads", RiskLevel.LOW),
            ("leads.lead.create_self_generated", "Create self-generated lead", RiskLevel.LOW),
            ("leads.lead.create_any_source", "Create lead from any source", RiskLevel.MEDIUM),
            ("leads.lead.create_from_self_generated", "Create lead: Self-Generated", RiskLevel.LOW),
            ("leads.lead.create_from_campaign", "Create lead: Campaign", RiskLevel.MEDIUM),
            ("leads.lead.create_from_broker", "Create lead: Broker", RiskLevel.MEDIUM),
            ("leads.lead.create_from_walk_in", "Create lead: Walk-in", RiskLevel.MEDIUM),
            ("leads.lead.create_from_call_center", "Create lead: Call Center", RiskLevel.MEDIUM),
            ("leads.lead.create_from_exhibition", "Create lead: Exhibition", RiskLevel.MEDIUM),
            ("leads.lead.create_from_referral", "Create lead: Referral", RiskLevel.MEDIUM),
            ("leads.lead.create_from_existing_client", "Create lead: Existing Client", RiskLevel.MEDIUM),
            ("leads.lead.view_own", "View own leads", RiskLevel.LOW),
            ("leads.lead.view_team", "View team leads", RiskLevel.MEDIUM),
            ("leads.lead.view_all", "View all leads", RiskLevel.HIGH),
            ("leads.distribution.manual_all", "Manual distribution (all)", RiskLevel.HIGH),
            ("leads.distribution.team_manual", "Manual distribution (team)", RiskLevel.MEDIUM),
            ("leads.stage.change_own", "Change stage (own)", RiskLevel.LOW),
            ("leads.followup.create_own", "Create follow-up", RiskLevel.LOW),
            ("leads.meeting.create_own", "Create meeting", RiskLevel.LOW),
            ("marketing.campaigns.access", "Open campaigns", RiskLevel.LOW),
            ("marketing.campaign.create", "Create campaign", RiskLevel.MEDIUM),
            ("marketing.campaign.update", "Update campaign", RiskLevel.MEDIUM),
            ("marketing.campaign.delete", "Delete campaign", RiskLevel.HIGH),
            ("marketing.campaign.view_all", "View all campaigns", RiskLevel.MEDIUM),
            ("marketing.budget.manage", "Manage budget", RiskLevel.HIGH),
            ("marketing.campaign.submit_finance", "Submit to finance", RiskLevel.MEDIUM),
            ("finance.dashboard.access", "Open finance", RiskLevel.MEDIUM),
            ("finance.campaign.review", "Review campaign", RiskLevel.MEDIUM),
            ("finance.campaign.approve", "Approve campaign", RiskLevel.HIGH),
            ("authorization.roles.manage", "Manage roles", RiskLevel.HIGH),
            ("authorization.permissions.manage", "Manage permissions", RiskLevel.HIGH),
            ("policies.company.manage", "Manage policies", RiskLevel.HIGH),
            ("audit.view_all", "View audit log", RiskLevel.HIGH),
            ("notifications.view_own", "View notifications", RiskLevel.LOW),
            ("integrations.webhooks.manage", "Manage webhooks", RiskLevel.HIGH),
        ]
        for code, name, risk in codes:
            module = code.split(".")[0]
            parts = code.split(".")
            page_code = f"{parts[0]}.{parts[1]}"
            page = PageDefinition.objects.filter(code=page_code).first()
            if not page:
                page = PageDefinition.objects.filter(
                    code__startswith=f"{module}."
                ).first()
            PermissionDefinition.objects.update_or_create(
                code=code,
                defaults=dict(module=module, action=code.rsplit(".", 1)[-1],
                              name=name, page=page, risk_level=risk),
            )
        self.stdout.write(f"  permissions: {len(codes)}")

    def _role_defaults(self, company):
        """Seed default permission bundles per role (docs §5.2). Editable by
        admins afterwards through the UI — these are starting defaults only."""
        from apps.authorization.models import (
            PermissionDefinition,
            RoleGroup,
            RolePermission,
        )

        all_codes = list(
            PermissionDefinition.objects.values_list("code", flat=True)
        )
        # Source-level create permission codes (leads spec §4.2b role defaults).
        all_source_creates = [f"leads.lead.create_from_{s.lower()}" for s in SourceCode.ALL]
        bundles = {
            "SYSTEM_ADMINS": all_codes,
            "DIRECTORS": ["dashboard.main.access", "leads.dashboard.access",
                          "leads.lead.view_all", "leads.distribution.manual_all",
                          "notifications.view_own", *all_source_creates],
            "SALES": ["dashboard.main.access", "leads.dashboard.access",
                      "leads.lead.create_self_generated",
                      "leads.lead.create_from_self_generated", "leads.lead.view_own",
                      "leads.stage.change_own", "leads.followup.create_own",
                      "leads.meeting.create_own", "notifications.view_own"],
            "SALES_HEAD": ["dashboard.main.access", "leads.dashboard.access",
                           "leads.lead.create_self_generated",
                           "leads.lead.create_from_self_generated", "leads.lead.view_own",
                           "leads.lead.view_team", "leads.distribution.team_manual",
                           "leads.stage.change_own", "leads.followup.create_own",
                           "leads.meeting.create_own", "notifications.view_own"],
            "SALES_OPERATION": ["dashboard.main.access", "leads.dashboard.access",
                                "leads.lead.view_all", "leads.lead.create_any_source",
                                "leads.distribution.manual_all", "notifications.view_own",
                                "admin.teams.access", "admin.teams.create",
                                "admin.teams.update", "admin.teams.delete",
                                # All sources except self-generated (§4.2b).
                                *[c for c in all_source_creates
                                  if c != "leads.lead.create_from_self_generated"]],
            "CALL_CENTER": ["dashboard.main.access", "leads.dashboard.access",
                            "leads.lead.create_from_call_center",
                            "leads.lead.create_from_existing_client",
                            "leads.lead.view_own", "notifications.view_own"],
            "BROKERS": ["dashboard.main.access", "leads.dashboard.access",
                        "leads.lead.create_from_broker", "leads.lead.view_own",
                        "notifications.view_own"],
            "RECEPTIONISTS": ["dashboard.main.access", "leads.dashboard.access",
                              "leads.lead.create_from_walk_in", "notifications.view_own"],
            "FINANCE_MANAGERS": ["finance.dashboard.access", "finance.campaign.review",
                                 "finance.campaign.approve",
                                 "marketing.campaign.view_all", "notifications.view_own"],
            "MARKETING_MEMBERS": ["marketing.campaigns.access",
                                  "marketing.campaign.create",
                                  "marketing.campaign.update", "marketing.budget.manage",
                                  "marketing.campaign.submit_finance",
                                  "notifications.view_own"],
            "MARKETING_MANAGERS": ["marketing.campaigns.access",
                                   "marketing.campaign.create",
                                   "marketing.campaign.update",
                                   "marketing.campaign.delete",
                                   "marketing.campaign.view_all",
                                   "marketing.budget.manage",
                                   "marketing.campaign.submit_finance",
                                   "notifications.view_own"],
        }
        perms = {p.code: p for p in PermissionDefinition.objects.all()}
        for role_code, codes in bundles.items():
            role = RoleGroup.objects.filter(company=company, code=role_code).first()
            if role is None:
                continue
            for code in codes:
                if code in perms:
                    RolePermission.objects.update_or_create(
                        role=role, permission=perms[code], defaults={"allow": True}
                    )
        self.stdout.write(f"  role default bundles: {len(bundles)}")

    def _say(self, label, created):
        state = "created" if created else "exists"
        self.stdout.write(f"  {label}: {state}")

    @staticmethod
    def _slug(name):
        return slugify(name)
