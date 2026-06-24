"""Policy resolution (docs §7). Single seam services use to read configurable
rules; nothing hardcodes SLA times, distribution methods, or budget rules (§8)."""
from __future__ import annotations

from typing import Any

from apps.core.exceptions import PolicyError

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


class PolicyManagementService:
    @staticmethod
    def set_value(*, company, code: str, option=None, value_json=None, updated_by=None,
                  effective_from=None):
        policy = PolicyDefinition.objects.get(code=code)
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
        return cpv
