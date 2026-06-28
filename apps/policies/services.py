"""Policy resolution (docs §7). Single seam services use to read configurable
rules; nothing hardcodes SLA times, distribution methods, or budget rules (§8)."""
from __future__ import annotations

import json
from typing import Any

from apps.core.exceptions import PolicyError

from .constants import ValueType
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
            h, m = v.get("hours", 0), v.get("minutes", 0)
            parts = []
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
            by_module.setdefault(p.module, []).append({
                "policy": p,
                "cpv": cpv,
                "current_display": _format_current(cpv, p.value_type),
                "is_set": cpv is not None and (
                    cpv.selected_option_id is not None or cpv.value_json is not None
                ),
            })
        # Ordered, display-friendly module groups for the policies page (task 13).
        meta = {
            "leads": ("Leads & Distribution", "Assignment, SLA and per-lead rules"),
            "marketing": ("Marketing", "Campaign budgets and approvals"),
            "notifications": ("Notifications", "Reminders and cleanup jobs"),
            "integration": ("Integrations", "Webhooks and external mappings"),
        }
        order = ["leads", "marketing", "notifications", "integration"]
        modules = []
        for key in order + [m for m in by_module if m not in order]:
            rows = by_module.get(key)
            if not rows:
                continue
            title, desc = meta.get(key, (key.title(), ""))
            modules.append({
                "key": key, "title": title, "description": desc, "rows": rows,
                "count": len(rows),
                "set_count": sum(1 for r in rows if r["is_set"]),
            })
        total = sum(m["count"] for m in modules)
        configured = sum(m["set_count"] for m in modules)
        return {"by_module": by_module, "modules": modules,
                "total_policies": total, "configured_policies": configured}

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
            h = int(post_data.get("hours", 0) or 0)
            m = int(post_data.get("minutes", 0) or 0)
            value_json = {"hours": h, "minutes": m}

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

        PolicyManagementService.set_value(
            company=company, code=policy.code,
            option=option, value_json=value_json,
            updated_by=updated_by, request_meta=request_meta,
        )
