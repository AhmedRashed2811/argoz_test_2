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
            (PolicyCode.WALKIN_SLA, "Walk-in Lead SLA", "leads", ValueType.DURATION, []),
            (PolicyCode.SLA_EXPIRY_METHOD, "SLA Expiry Method", "leads", ValueType.OPTION,
             [(SLAExpiryMethod.ROUND_ROBIN, "Round Robin", "ROUND_ROBIN"),
              (SLAExpiryMethod.BY_TURN, "By Turn", "BY_TURN"),
              (SLAExpiryMethod.RETRY_TEAM_ESCALATION, "Retry + Team Escalation", ""),
              (SLAExpiryMethod.MANUAL, "Manual", "")]),
            (PolicyCode.DEFAULT_AUTO_DISTRIBUTION_METHOD, "Auto Distribution Method",
             "leads", ValueType.OPTION,
             [("ROUND_ROBIN", "Round Robin", "ROUND_ROBIN"),
              ("BY_TURN", "By Turn", "BY_TURN")]),
            (PolicyCode.BULK_IMPORT_DISTRIBUTION, "Bulk Import Distribution", "leads",
             ValueType.OPTION,
             [("AUTO", "Automatic distribution", ""),
              ("MANUAL", "Manual distribution only", "")]),
            (PolicyCode.DISTRIBUTION_SCOPE_MODE, "Distribution Scope Mode", "leads",
             ValueType.OPTION,
             [(ScopeMode.TEAM_THEN_SALESMAN, "Team then Salesman", ""),
              (ScopeMode.TEAM_HEAD_DECIDES, "Team, Head Decides", ""),
              (ScopeMode.ALL_SALESMEN, "All Salesmen", "")]),
            (PolicyCode.RETRY_ATTEMPTS_PER_TEAM, "Retry Attempts per Team", "leads",
             ValueType.INTEGER, []),
            (PolicyCode.LANGUAGE_DEFAULT, "Default Language", "leads", ValueType.CODE, []),
            (PolicyCode.SELF_GENERATED_SALESMAN_POLICY, "Self-Generated Salesman Policy",
             "leads", ValueType.OPTION,
             [("KEEP_WITH_OWNER", "Keep with owner", ""),
              ("REDISTRIBUTE_AFTER_SLA", "Redistribute after SLA", "")]),
            (PolicyCode.SELF_GENERATED_HEAD_ASSIGNMENT,
             "Self-Generated Head Assignment", "leads", ValueType.OPTION,
             [("SELF_OR_MANUAL_TEAM", "Self or manual team member", ""),
              ("AUTO_ROUND_ROBIN_TEAM", "Auto round-robin within team", ""),
              ("SELF_ONLY", "Self Only", "")]),
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
             ValueType.DURATION, []),
            (PolicyCode.CAMPAIGN_RESTRICT_EDITING, "Restrict Approved Campaign Editing", "marketing",
             ValueType.BOOLEAN, []),
            (PolicyCode.REQUEST_CAMPAIGN_APPROVAL, "Request Campaign Approval", "marketing",
             ValueType.BOOLEAN, []),
            (PolicyCode.WEBHOOK_MAPPING_POLICY, "Webhook Mapping Policy", "integration",
             ValueType.JSON, []),
            # Composite On/Off policies (task 16) — default Off, configured in the
            # policy editor; schema in apps/policies/composite.py.
            (PolicyCode.SALES_ACTION_LIMITS,
             "Per-Lead Action Limits (Sales)", "leads", ValueType.COMPOSITE, []),
            (PolicyCode.SALES_ACTION_MAX_DURATION,
             "Per-Lead Action Time Limits (Sales)", "leads", ValueType.COMPOSITE, []),
            (PolicyCode.NOTIFICATION_AUTO_CLEANUP,
             "Old Notification Cleanup", "notifications", ValueType.COMPOSITE, []),
            (PolicyCode.DAILY_TASK_EMAIL,
             "Daily Task Reminder Email", "notifications", ValueType.COMPOSITE, []),
            (PolicyCode.WEEKEND_SLA_FREEZE,
             "Weekend SLA Freeze", "leads", ValueType.COMPOSITE, []),
            # Task 1a: per-salesman stage capacity caps (On/Off, default Off).
            (PolicyCode.SALES_STAGE_CAPACITY,
             "Per-Salesman Stage Capacity", "leads", ValueType.COMPOSITE, []),
            # Task 1b: salesman sees their inactive leads (default On).
            (PolicyCode.SALES_VIEW_INACTIVE,
             "Salesman Sees Inactive Leads", "leads", ValueType.BOOLEAN, []),
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
        self._select(company, PolicyCode.SLA_EXPIRY_METHOD, SLAExpiryMethod.BY_TURN)
        self._select(company, PolicyCode.DEFAULT_AUTO_DISTRIBUTION_METHOD, "BY_TURN")
        self._select(company, PolicyCode.BULK_IMPORT_DISTRIBUTION, "MANUAL")
        self._select(company, PolicyCode.DISTRIBUTION_SCOPE_MODE, ScopeMode.ALL_SALESMEN)
        self._select(company, PolicyCode.WALKIN_RECEPTION_POLICY, "FULL_ROTATION")
        self._select(company, PolicyCode.EXISTING_CLIENT_POLICY,
                     "PRESERVE_PRIOR_RELATIONSHIP")
        self._set_value(company, PolicyCode.LANGUAGE_DEFAULT, {"code": "ar"})
        self._set_value(company, PolicyCode.DIRECT_SLA, {"minutes": 5})
        self._set_value(company, PolicyCode.BROKER_SLA, {"minutes": 5})
        self._set_value(company, PolicyCode.WALKIN_SLA, {"hours": 24})
        self._set_value(company, f"{PolicyCode.STAGE_SLA}.fresh", {"hours": 2})
        self._select(company, PolicyCode.SELF_GENERATED_SALESMAN_POLICY, "KEEP_WITH_OWNER")
        self._select(company, PolicyCode.SELF_GENERATED_HEAD_ASSIGNMENT,
                     "SELF_OR_MANUAL_TEAM")
        self._set_value(company, PolicyCode.BROKER_ALSO_ASSIGN_SALESMAN, True)
        self._set_value(company, PolicyCode.FRESH_REMINDER_SCHEDULE, {"minutes": 2})
        self._set_value(company, PolicyCode.CAMPAIGN_RESTRICT_EDITING, True)
        self._set_value(company, PolicyCode.REQUEST_CAMPAIGN_APPROVAL, True)
        self._select(company, PolicyCode.NOT_REACHED_REMINDER_MODE, "AUTOMATIC")
        # Task 1b default: salesmen see their inactive leads unless turned off.
        self._set_value(company, PolicyCode.SALES_VIEW_INACTIVE, True)
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
        # menu_order is now a single global sequence (nav orders by menu_order),
        # grouped for UX: daily lead work → marketing → finance → admin.
        pages = [
            ("dashboard", "main", "Dashboard", "dashboard:index", 0, None),
            # — Leads workspace —
            ("leads", "dashboard", "Leads", "leads:list", 10, None),
            ("leads", "calendar", "Calendar", "leads:calendar", 15, None),
            ("leads", "create", "Add Lead", "leads:create", 11, "leads.dashboard"),
            ("leads", "manual_distribution", "Manual Distribution",
             "leads:manual_distribution", 12, "leads.dashboard"),
            ("leads", "sales_performance", "Sales Performance",
             "leads:sales_performance", 13, "leads.dashboard"),
            ("leads", "leads_analysis", "Leads Analysis",
             "leads:leads_analysis", 14, "leads.dashboard"),
            # — Marketing —
            ("marketing", "campaigns", "Campaigns", "marketing:campaign_list", 20, None),
            ("marketing", "marketing_report", "Marketing Reports",
             "marketing:marketing_report", 21, "marketing.campaigns"),
            # — Finance —
            ("finance", "dashboard", "Finance Approvals", "finance:campaign_approval", 30, None),
            # — Notifications —
            ("notifications", "view_own", "Notifications", "notifications:list", 40, None),
            # — Administration —
            # People & access group (task 12): header-only parent grouping Users,
            # Sales Teams and Roles & Permissions under one collapsible section.
            ("admin", "people", "People & Access", "", 49, None),
            ("admin", "users", "Users", "accounts:user_list", 50, "admin.people"),
            ("admin", "teams", "Sales Teams", "accounts:team_list", 51, "admin.people"),
            ("admin", "brokers", "Brokers", "accounts:broker_list", 52, None),
            ("authorization", "roles", "Roles & Permissions",
             "authorization:role_list", 53, "admin.people"),
            ("policies", "company", "Policies", "policies:list", 54, None),
            ("audit", "view_all", "Audit Log", "audit:list", 55, None),
            ("integrations", "webhooks", "Webhooks", "integrations:webhook_list", 56, None),
        ]
        valid_codes = {f"{m}.{c}" for m, c, *_ in pages}
        for module, code, name, url_name, order, _ in pages:
            PageDefinition.objects.update_or_create(
                code=f"{module}.{code}",
                defaults=dict(module=module, name=name, url_name=url_name,
                              menu_order=order, is_menu_item=(module != "notifications")),
            )
        for module, code, _, _, _, parent_code in pages:
            page = PageDefinition.objects.filter(code=f"{module}.{code}").first()
            if page:
                if parent_code:
                    page.parent = PageDefinition.objects.filter(code=parent_code).first()
                else:
                    page.parent = None
                page.save()
        # Prune stale top-level menu rows (e.g. a duplicate "Marketing Reports"
        # left over from an earlier seed) so the sidebar matches this list.
        PageDefinition.objects.filter(parent__isnull=True).exclude(
            code__in=valid_codes
        ).delete()
        self.stdout.write(f"  pages: {len(pages)}")

    def _permissions(self):
        from apps.authorization.models import PageDefinition, PermissionDefinition, RiskLevel

        # Every code referenced by view decorators / selectors (docs §5.1).
        codes = [
            ("admin.users.access", "Open users page", RiskLevel.MEDIUM),
            ("admin.users.create", "Create users", RiskLevel.MEDIUM),
            ("admin.users.update", "Update users", RiskLevel.MEDIUM),
            ("admin.users.delete", "Delete users", RiskLevel.HIGH),
            ("admin.teams.access", "Open sales teams page", RiskLevel.LOW),
            ("admin.teams.create", "Create sales teams", RiskLevel.MEDIUM),
            ("admin.teams.update", "Update sales teams", RiskLevel.MEDIUM),
            ("admin.teams.delete", "Deactivate sales teams", RiskLevel.HIGH),
            ("admin.brokers.access", "Open brokers page", RiskLevel.LOW),
            ("admin.brokers.create", "Create brokers", RiskLevel.MEDIUM),
            ("leads.dashboard.access", "Open leads", RiskLevel.LOW),
            ("leads.calendar.access", "Open calendar", RiskLevel.LOW),
            ("leads.lead.create", "Create lead", RiskLevel.LOW),
            ("leads.lead.bulk_create", "Bulk import leads (CSV)", RiskLevel.MEDIUM),
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
            ("leads.lead.edit_all", "Edit any lead", RiskLevel.HIGH),
            ("leads.lead.deactivate", "Activate/deactivate lead", RiskLevel.HIGH),
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
            ("finance.campaign.review", "Review campaign", RiskLevel.MEDIUM),
            ("finance.campaign.approve", "Approve campaign", RiskLevel.HIGH),
            ("authorization.roles.manage", "Manage roles", RiskLevel.HIGH),
            ("authorization.permissions.manage", "Manage permissions", RiskLevel.HIGH),
            ("policies.company.manage", "Manage policies", RiskLevel.HIGH),
            ("audit.view_all", "View audit log", RiskLevel.HIGH),
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
        # Nav gate for the Manual Distribution page: link both distribution
        # permissions to it so _page_allowed() shows the menu item for either
        # manual_all (any salesman) or team_manual (own team) holders.
        md_page = PageDefinition.objects.filter(
            code="leads.manual_distribution"
        ).first()
        if md_page:
            PermissionDefinition.objects.filter(
                code__in=["leads.distribution.manual_all",
                          "leads.distribution.team_manual"]
            ).update(page=md_page)
        create_page = PageDefinition.objects.filter(
            code="leads.create"
        ).first()
        if create_page:
            PermissionDefinition.objects.filter(
                code="leads.lead.create"
            ).update(page=create_page)
        # Marketing report gate (review_marketing_report). Flat code, linked to
        # the report page so _page_allowed() surfaces the menu item for holders.
        report_page = PageDefinition.objects.filter(
            code="marketing.marketing_report"
        ).first()
        PermissionDefinition.objects.update_or_create(
            code="review_marketing_report",
            defaults=dict(module="marketing", action="review_marketing_report",
                          name="Review marketing report", page=report_page,
                          risk_level=RiskLevel.MEDIUM),
        )
        # Sales performance report gate (review_sales_performance_report). Flat
        # code linked to its page so _page_allowed() surfaces the menu item.
        perf_page = PageDefinition.objects.filter(
            code="leads.sales_performance"
        ).first()
        PermissionDefinition.objects.update_or_create(
            code="review_sales_performance_report",
            defaults=dict(module="leads", action="review_sales_performance_report",
                          name="Review sales performance report", page=perf_page,
                          risk_level=RiskLevel.MEDIUM),
        )
        # Leads analysis report gate (review_leads_analysis). Flat code linked to
        # its page so _page_allowed() surfaces the menu item for holders.
        analysis_page = PageDefinition.objects.filter(
            code="leads.leads_analysis"
        ).first()
        PermissionDefinition.objects.update_or_create(
            code="review_leads_analysis",
            defaults=dict(module="leads", action="review_leads_analysis",
                          name="Review leads analysis", page=analysis_page,
                          risk_level=RiskLevel.MEDIUM),
        )
        self.stdout.write(f"  permissions: {len(codes) + 3}")

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
            "DIRECTORS": ["leads.dashboard.access",
                          "leads.lead.create", "leads.lead.view_all", "leads.lead.edit_all",
                          "leads.lead.deactivate", "leads.stage.change_own",
                          "leads.distribution.manual_all",
                          "review_marketing_report",
                          "review_sales_performance_report",
                          "review_leads_analysis",
                          # Oversight of System Admins: only Directors may edit the
                          # System Admins role / a System Admin's permissions (§4.4).
                          "authorization.roles.manage",
                          "authorization.permissions.manage",
                          "admin.users.access", *all_source_creates,
                          "admin.brokers.access", "admin.brokers.create"],
            "SALES": ["leads.dashboard.access", "leads.calendar.access",
                      "leads.lead.create", "leads.lead.create_self_generated",
                      "leads.lead.create_from_self_generated", "leads.lead.view_own",
                      "leads.stage.change_own", "leads.followup.create_own",
                      "leads.meeting.create_own"],
            "SALES_HEAD": ["leads.dashboard.access", "leads.calendar.access",
                           "leads.lead.create", "leads.lead.create_self_generated",
                           "leads.lead.create_from_self_generated", "leads.lead.view_own",
                           "leads.lead.view_team", "leads.distribution.team_manual",
                           "leads.stage.change_own", "leads.followup.create_own",
                           "leads.meeting.create_own",
                           "review_sales_performance_report"],
            "SALES_OPERATION": ["leads.dashboard.access",
                                "leads.lead.create", "leads.lead.view_all", "leads.lead.edit_all",
                                "leads.lead.deactivate", "leads.stage.change_own",
                                "leads.lead.create_any_source",
                                "leads.distribution.manual_all",
                                "review_leads_analysis",
                                "admin.teams.access", "admin.teams.create",
                                "admin.teams.update", "admin.teams.delete",
                                "admin.brokers.access", "admin.brokers.create",
                                # All sources except self-generated (§4.2b).
                                *[c for c in all_source_creates
                                  if c != "leads.lead.create_from_self_generated"]],
            # Capture-only: only the Call Center source (default on the restricted page).
            "CALL_CENTER": ["leads.dashboard.access",
                            "leads.lead.create", "leads.lead.create_from_call_center",
                            "leads.lead.view_own"],
            "BROKERS": ["leads.dashboard.access",
                        "leads.lead.create", "leads.lead.create_from_broker", "leads.lead.view_own"],
            # Capture-only: Walk-in (default) + Existing Client sources.
            "RECEPTIONISTS": ["leads.dashboard.access",
                              "leads.lead.create", "leads.lead.create_from_walk_in",
                              "leads.lead.create_from_existing_client"],
            "FINANCE_MANAGERS": ["finance.campaign.review",
                                 "finance.campaign.approve",
                                 "marketing.campaign.view_all",
                                 "review_marketing_report",
                                 "review_leads_analysis"],
            "MARKETING_MEMBERS": ["marketing.campaigns.access",
                                  "marketing.campaign.create",
                                  "marketing.campaign.update", "marketing.budget.manage",
                                  "marketing.campaign.submit_finance"],
            "MARKETING_MANAGERS": ["marketing.campaigns.access",
                                   "marketing.campaign.create",
                                   "marketing.campaign.update",
                                   "marketing.campaign.delete",
                                   "marketing.campaign.view_all",
                                   "marketing.budget.manage",
                                   "marketing.campaign.submit_finance",
                                   "review_marketing_report",
                                   "review_leads_analysis"],
        }
        # Bulk import follows single-lead create: any group that can create a lead
        # gets bulk_create by default (admins can change it afterwards). Capture-only
        # roles (Call Center / Receptionist / Broker) are excluded — they use the
        # restricted single-lead create page and may not import CSVs.
        _no_bulk = {"CALL_CENTER", "RECEPTIONISTS", "BROKERS"}
        for role_code, codes in bundles.items():
            if role_code in _no_bulk:
                continue
            if "leads.lead.create" in codes and "leads.lead.bulk_create" not in codes:
                codes.append("leads.lead.bulk_create")
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
