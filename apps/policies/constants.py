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
    WEBHOOK_MAPPING_POLICY = "integration.webhook_mapping_policy"


class ValueType:
    OPTION = "OPTION"
    DURATION = "DURATION"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    JSON = "JSON"
    CODE = "CODE"
    CHOICES = [
        (OPTION, "Option"),
        (DURATION, "Duration"),
        (INTEGER, "Integer"),
        (BOOLEAN, "Boolean"),
        (JSON, "JSON"),
        (CODE, "Code"),
    ]
