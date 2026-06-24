"""Stable internal codes shared across apps (docs §5 wants stable codes, not
role-name if/else). Domain-specific codes live in their own app's constants."""


class AuditAction:
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ASSIGN = "ASSIGN"
    STAGE_CHANGE = "STAGE_CHANGE"
    SLA_EVENT = "SLA_EVENT"
    APPROVE = "APPROVE"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    POLICY_CHANGE = "POLICY_CHANGE"
    BUDGET_CHANGE = "BUDGET_CHANGE"
    WEBHOOK_EVENT = "WEBHOOK_EVENT"
    JOB_RESULT = "JOB_RESULT"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    LOGIN = "LOGIN"

    CHOICES = [
        (CREATE, "Create"),
        (UPDATE, "Update"),
        (DELETE, "Delete"),
        (ASSIGN, "Assign"),
        (STAGE_CHANGE, "Stage change"),
        (SLA_EVENT, "SLA event"),
        (APPROVE, "Approve"),
        (PERMISSION_CHANGE, "Permission change"),
        (POLICY_CHANGE, "Policy change"),
        (BUDGET_CHANGE, "Budget change"),
        (WEBHOOK_EVENT, "Webhook event"),
        (JOB_RESULT, "Job result"),
        (IMPORT, "Import"),
        (EXPORT, "Export"),
        (LOGIN, "Login"),
    ]
