"""Stable policy codes from the required catalog (docs §7.2). Services resolve
behavior by these codes; the business team edits values via UI, no code change."""


class PolicyCode:
    DIRECT_SLA = "lead.origin.direct_sla"
    BROKER_SLA = "lead.origin.broker_sla"
    WALKIN_SLA = "lead.origin.walkin_sla"
    STAGE_SLA = "lead.stage_sla"  # suffixed with .<stage_code>
    SLA_EXPIRY_METHOD = "lead.sla_expiry_method"
    RETRY_ATTEMPTS_PER_TEAM = "lead.retry_attempts_per_team"
    DEFAULT_AUTO_DISTRIBUTION_METHOD = "lead.default_auto_distribution_method"
    BULK_IMPORT_DISTRIBUTION = "lead.bulk_import_distribution"
    DISTRIBUTION_SCOPE_MODE = "lead.distribution_scope_mode"
    LANGUAGE_DEFAULT = "lead.language_default"
    SELF_GENERATED_SALESMAN_POLICY = "lead.self_generated_salesman_policy"
    SELF_GENERATED_HEAD_ASSIGNMENT = "lead.self_generated_head_assignment"
    BROKER_ALSO_ASSIGN_SALESMAN = "lead.broker_also_assign_salesman"
    WALKIN_RECEPTION_POLICY = "lead.walkin_reception_policy"
    EXISTING_CLIENT_POLICY = "lead.existing_client_policy"
    NOT_REACHED_REMINDER_MODE = "lead.not_reached_reminder_mode"
    FRESH_REMINDER_SCHEDULE = "lead.fresh_reminder_schedule"
    BUDGET_CALCULATION_RULE = "marketing.budget_calculation_rule"
    CAMPAIGN_RESTRICT_EDITING = "marketing.restrict_approved_campaign_editing"
    REQUEST_CAMPAIGN_APPROVAL = "marketing.request_campaign_approval"
    WEBHOOK_MAPPING_POLICY = "integration.webhook_mapping_policy"
    # Composite On/Off policies (task 16). Each stores a dict in value_json with
    # an "enabled" flag (default False) plus its configured fields.
    SALES_ACTION_LIMITS = "lead.sales_action_limits"             # 16a
    SALES_ACTION_MAX_DURATION = "lead.sales_action_max_duration"  # 16b
    NOTIFICATION_AUTO_CLEANUP = "notification.auto_cleanup"       # 16c
    DAILY_TASK_EMAIL = "notification.daily_task_email"            # 16d
    WEEKEND_SLA_FREEZE = "lead.weekend_sla_freeze"               # 16e


class ValueType:
    OPTION = "OPTION"
    DURATION = "DURATION"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    JSON = "JSON"
    CODE = "CODE"
    COMPOSITE = "COMPOSITE"  # On/Off toggle + structured fields (task 16)
    CHOICES = [
        (OPTION, "Option"),
        (DURATION, "Duration"),
        (INTEGER, "Integer"),
        (BOOLEAN, "Boolean"),
        (JSON, "JSON"),
        (CODE, "Code"),
        (COMPOSITE, "Composite"),
    ]
