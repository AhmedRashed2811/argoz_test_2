"""Policy resolution (docs §7). Single seam services use to read configurable
rules; nothing hardcodes SLA times, distribution methods, or budget rules (§8)."""
from __future__ import annotations

import json
from typing import Any

from apps.core.exceptions import PolicyError

from .constants import PolicyCode, ValueType
from .models import CompanyPolicyValue, PolicyDefinition


class PolicyResolver:
    @staticmethod
    def _value(company, code: str) -> CompanyPolicyValue | None:
        return (
            CompanyPolicyValue.objects.select_related("selected_option", "policy")
            .filter(company=company, policy__code=code, policy__is_active=True)
            .first()
        )

    @classmethod
    def option_code(cls, company, code: str, default: str | None = None) -> str | None:
        cpv = cls._value(company, code)
        if cpv and cpv.selected_option:
            return cpv.selected_option.code
        if cpv and isinstance(cpv.value_json, dict):
            return cpv.value_json.get("code", default)
        return default

    @classmethod
    def strategy_code(cls, company, code: str, default: str | None = None) -> str | None:
        cpv = cls._value(company, code)
        if cpv and cpv.selected_option and cpv.selected_option.strategy_code:
            return cpv.selected_option.strategy_code
        return default

    @classmethod
    def value(cls, company, code: str, default: Any = None) -> Any:
        cpv = cls._value(company, code)
        if cpv is None:
            return default
        if cpv.value_json is not None:
            return cpv.value_json
        if cpv.selected_option:
            return cpv.selected_option.code
        return default

    @classmethod
    def param(cls, company, code: str, key: str, default: Any = None) -> Any:
        cpv = cls._value(company, code)
        if cpv is None:
            return default
        param = cpv.parameters.filter(key=key).first()
        return param.value_json if param else default

    @classmethod
    def require_value(cls, company, code: str) -> Any:
        val = cls.value(company, code, default=None)
        if val is None:
            raise PolicyError(f"Policy not configured: {code}")
        return val


def _format_current(cpv: CompanyPolicyValue | None, value_type: str) -> str:
    if cpv is None:
        return ""
    if cpv.selected_option:
        return cpv.selected_option.label
    if cpv.value_json is not None:
        v = cpv.value_json
        if value_type == ValueType.DURATION and isinstance(v, dict):
            d, h, m = v.get("days", 0), v.get("hours", 0), v.get("minutes", 0)
            parts = []
            if d:
                parts.append(f"{d}d")
            if h:
                parts.append(f"{h}h")
            if m:
                parts.append(f"{m}m")
            return " ".join(parts) or "0h"
        if value_type == ValueType.BOOLEAN:
            return "Yes" if v else "No"
        if value_type == ValueType.COMPOSITE and isinstance(v, dict):
            return "On" if v.get("enabled") else "Off"
        return json.dumps(v)
    return ""


class PolicyManagementService:
    MODULE_META = {
        "leads": ("Leads & Distribution", "Assignment, SLA and daily lead rules"),
        "marketing": ("Marketing", "Campaign approvals and editing rules"),
        "notifications": ("Notifications", "Reminders, emails and cleanup jobs"),
        "integration": ("Integrations", "Webhooks and external mappings"),
    }
    MODULE_ORDER = ["leads", "marketing", "notifications", "integration"]

    POLICY_GROUPS = [
        {
            "key": "lead-intake",
            "title": "Lead intake",
            "description": "Defaults used when a new lead enters the CRM.",
            "codes": {
                PolicyCode.LANGUAGE_DEFAULT,
                PolicyCode.BROKER_ALSO_ASSIGN_SALESMAN,
                PolicyCode.EXISTING_CLIENT_POLICY,
            },
        },
        {
            "key": "assignment-routing",
            "title": "Assignment and routing",
            "description": "How leads move between teams, salesmen and reception.",
            "codes": {
                PolicyCode.DEFAULT_AUTO_DISTRIBUTION_METHOD,
                PolicyCode.BULK_IMPORT_DISTRIBUTION,
                PolicyCode.DISTRIBUTION_SCOPE_MODE,
                PolicyCode.RETRY_ATTEMPTS_PER_TEAM,
                PolicyCode.SELF_GENERATED_SALESMAN_POLICY,
                PolicyCode.SELF_GENERATED_HEAD_ASSIGNMENT,
                PolicyCode.WALKIN_RECEPTION_POLICY,
            },
        },
        {
            "key": "sla-timing",
            "title": "SLA timing",
            "description": "Response windows by origin and lead stage.",
            "codes": {
                PolicyCode.DIRECT_SLA,
                PolicyCode.BROKER_SLA,
                PolicyCode.WALKIN_SLA,
                PolicyCode.SLA_EXPIRY_METHOD,
                PolicyCode.FRESH_REMINDER_SCHEDULE,
                PolicyCode.WEEKEND_SLA_FREEZE,
            },
            "prefixes": [f"{PolicyCode.STAGE_SLA}."],
        },
        {
            "key": "sales-actions",
            "title": "Sales actions",
            "description": "Follow-up, meeting, freeze and reminder limits.",
            "codes": {
                PolicyCode.NOT_REACHED_REMINDER_MODE,
                PolicyCode.SALES_ACTION_LIMITS,
                PolicyCode.SALES_ACTION_MAX_DURATION,
                PolicyCode.SALES_STAGE_CAPACITY,
                PolicyCode.SALES_VIEW_INACTIVE,
            },
        },
        {
            "key": "campaign-controls",
            "title": "Campaign controls",
            "description": "Marketing approval and edit rules.",
            "codes": {
                PolicyCode.CAMPAIGN_RESTRICT_EDITING,
                PolicyCode.REQUEST_CAMPAIGN_APPROVAL,
            },
        },
        {
            "key": "notification-automation",
            "title": "Notification automation",
            "description": "Email reminders and notification maintenance.",
            "codes": {
                PolicyCode.NOTIFICATION_AUTO_CLEANUP,
                PolicyCode.DAILY_TASK_EMAIL,
            },
        },
        {
            "key": "webhook-mapping",
            "title": "Webhook mapping",
            "description": "External lead source mapping rules.",
            "codes": {PolicyCode.WEBHOOK_MAPPING_POLICY},
        },
    ]

    @classmethod
    def _policy_group_meta(cls, code: str) -> tuple[str, str, str]:
        for group in cls.POLICY_GROUPS:
            codes = group.get("codes", set())
            prefixes = group.get("prefixes", [])
            if code in codes or any(code.startswith(prefix) for prefix in prefixes):
                return group["key"], group["title"], group["description"]
        return "other", "Other settings", "Additional company policy settings."

    @staticmethod
    def _is_set(cpv: CompanyPolicyValue | None) -> bool:
        return cpv is not None and (
            cpv.selected_option_id is not None or cpv.value_json is not None
        )

    @staticmethod
    def get_list_context(*, company: Any) -> dict:
        values = {
            v.policy_id: v
            for v in CompanyPolicyValue.objects.filter(company=company)
            .select_related("selected_option")
        }
        policies = (
            PolicyDefinition.objects.filter(is_active=True)
            .prefetch_related("options")
            .order_by("module", "name")
        )
        by_module: dict[str, list] = {}
        for p in policies:
            cpv = values.get(p.id)
            group_key, group_title, group_desc = (
                PolicyManagementService._policy_group_meta(p.code)
            )
            by_module.setdefault(p.module, []).append({
                "policy": p,
                "cpv": cpv,
                "current_display": _format_current(cpv, p.value_type),
                "is_set": PolicyManagementService._is_set(cpv),
                "group_key": group_key,
                "group_title": group_title,
                "group_description": group_desc,
            })
        modules = []
        for key in (
            PolicyManagementService.MODULE_ORDER
            + [m for m in by_module if m not in PolicyManagementService.MODULE_ORDER]
        ):
            rows = by_module.get(key)
            if not rows:
                continue
            grouped_rows: dict[str, dict] = {}
            for row in rows:
                group = grouped_rows.setdefault(row["group_key"], {
                    "key": row["group_key"],
                    "title": row["group_title"],
                    "description": row["group_description"],
                    "rows": [],
                    "count": 0,
                    "set_count": 0,
                })
                group["rows"].append(row)
                group["count"] += 1
                group["set_count"] += 1 if row["is_set"] else 0
            group_order = {
                group["key"]: index
                for index, group in enumerate(PolicyManagementService.POLICY_GROUPS)
            }
            groups = sorted(
                grouped_rows.values(),
                key=lambda group: group_order.get(group["key"], 999),
            )
            title, desc = PolicyManagementService.MODULE_META.get(key, (key.title(), ""))
            modules.append({
                "key": key, "title": title, "description": desc, "rows": rows,
                "groups": groups,
                "count": len(rows),
                "set_count": sum(1 for r in rows if r["is_set"]),
            })
        total = sum(m["count"] for m in modules)
        configured = sum(m["set_count"] for m in modules)
        return {"by_module": by_module, "modules": modules,
                "total_policies": total, "configured_policies": configured}

    @staticmethod
    def get_value_summary(*, policy: PolicyDefinition,
                          cpv: CompanyPolicyValue | None) -> dict:
        is_set = PolicyManagementService._is_set(cpv)
        return {
            "policy_id": str(policy.id),
            "current_display": _format_current(cpv, policy.value_type),
            "is_set": is_set,
            "status_label": "Configured" if is_set else "Not configured",
        }

    @staticmethod
    def get_edit_context(*, policy_id: Any, company: Any) -> dict:
        policy = (
            PolicyDefinition.objects.prefetch_related("options")
            .get(id=policy_id)
        )
        cpv = (
            CompanyPolicyValue.objects.filter(company=company, policy=policy)
            .select_related("selected_option")
            .first()
        )
        composite = None
        if policy.value_type == ValueType.COMPOSITE:
            from .composite import schema_for_template
            composite = schema_for_template(
                policy.code, cpv.value_json if cpv else None
            )
        return {"policy": policy, "cpv": cpv, "value_type": policy.value_type,
                "composite": composite}

    @staticmethod
    def set_value(*, company, code: str, option=None, value_json=None,
                  updated_by=None, effective_from=None, request_meta=None):
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        policy = PolicyDefinition.objects.get(code=code)
        existing = CompanyPolicyValue.objects.filter(
            company=company, policy=policy
        ).select_related("selected_option").first()

        before = None
        if existing:
            before = {
                "option": existing.selected_option.label if existing.selected_option else None,
                "value_json": existing.value_json,
            }

        cpv, _ = CompanyPolicyValue.objects.update_or_create(
            company=company,
            policy=policy,
            defaults={
                "selected_option": option,
                "value_json": value_json,
                "updated_by": updated_by,
                "effective_from": effective_from,
            },
        )

        after = {
            "option": option.label if option else None,
            "value_json": value_json,
        }

        AuditService.log(
            action=AuditAction.POLICY_CHANGE,
            instance=cpv,
            actor=updated_by,
            company=company,
            module="policies",
            request_meta=request_meta,
            before=before,
            after=after,
            entity_display=policy.name,
        )
        return cpv

    @staticmethod
    def set_value_from_post(*, company, policy: PolicyDefinition, post_data,
                            updated_by=None, request_meta=None):
        """Parse POST data by value_type and delegate to set_value."""
        vtype = policy.value_type
        option = None
        value_json = None

        if vtype == ValueType.OPTION:
            code = post_data.get("option", "").strip()
            option = policy.options.filter(code=code).first() if code else None

        elif vtype == ValueType.DURATION:
            d = int(post_data.get("days", 0) or 0)
            h = int(post_data.get("hours", 0) or 0)
            m = int(post_data.get("minutes", 0) or 0)
            value_json = {"days": d, "hours": h, "minutes": m}

        elif vtype == ValueType.INTEGER:
            value_json = int(post_data.get("integer_value", 0) or 0)

        elif vtype == ValueType.BOOLEAN:
            value_json = post_data.get("bool_value") == "true"

        elif vtype == ValueType.CODE:
            value_json = {"code": post_data.get("code_value", "").strip()}

        elif vtype == ValueType.JSON:
            raw = post_data.get("value_json", "").strip()
            value_json = json.loads(raw) if raw else None

        elif vtype == ValueType.COMPOSITE:
            from .composite import parse_post
            value_json = parse_post(policy.code, post_data)

        cpv = PolicyManagementService.set_value(
            company=company, code=policy.code,
            option=option, value_json=value_json,
            updated_by=updated_by, request_meta=request_meta,
        )
        return PolicyManagementService.get_value_summary(policy=policy, cpv=cpv)
