"""Centralized audit writes (docs §6.2). Services call AuditService for semantic
events; DiffService computes field changes for simple CRUD. No scattered writes."""
from __future__ import annotations

from typing import Any

from django.forms.models import model_to_dict

from .models import AuditEventField, AuditLog


class DiffService:
    """Field-level before/after diff for simple CRUD (docs §6.2)."""

    @staticmethod
    def snapshot(instance, fields: list[str] | None = None) -> dict[str, Any]:
        data = model_to_dict(instance, fields=fields)
        return {k: _jsonable(v) for k, v in data.items()}

    @staticmethod
    def diff(before: dict, after: dict) -> dict[str, dict]:
        changed = {}
        for key in set(before) | set(after):
            old, new = before.get(key), after.get(key)
            if old != new:
                changed[key] = {"old": old, "new": new}
        return changed


class AuditService:
    @staticmethod
    def log(
        *,
        action: str,
        instance=None,
        entity_type: str = "",
        entity_id: str = "",
        actor=None,
        company=None,
        module: str = "",
        before: dict | None = None,
        after: dict | None = None,
        request_meta=None,
        reason: str = "",
        source: str = "",
        entity_display: str = "",
    ) -> AuditLog:
        if instance is not None:
            entity_type = entity_type or instance.__class__.__name__
            entity_id = entity_id or str(getattr(instance, "pk", ""))
            entity_display = entity_display or str(instance)[:255]
            if company is None:
                company = getattr(instance, "company", None)
        changed = DiffService.diff(before or {}, after or {}) if (before or after) else None
        log = AuditLog.objects.create(
            action=action,
            module=module,
            entity_type=entity_type,
            entity_id=str(entity_id),
            entity_display=entity_display,
            actor=actor,
            company=company,
            before_json=before,
            after_json=after,
            changed_fields=changed,
            request_meta=_meta_dict(request_meta),
            reason=reason,
            source=source,
        )
        if changed:
            AuditEventField.objects.bulk_create(
                [
                    AuditEventField(
                        audit=log,
                        field_name=name,
                        old_value=str(vals.get("old", "")),
                        new_value=str(vals.get("new", "")),
                    )
                    for name, vals in changed.items()
                ]
            )
        return log

    @staticmethod
    def log_change(*, actor, before, after, request_meta=None, **kwargs):
        """Convenience matching the docs §16 service pattern (before/after dicts)."""
        return AuditService.log(
            action=kwargs.pop("action", "UPDATE"),
            instance=after if not isinstance(after, dict) else None,
            actor=actor,
            before=before if isinstance(before, dict) else None,
            after=after if isinstance(after, dict) else None,
            request_meta=request_meta,
            **kwargs,
        )


def _meta_dict(request_meta):
    if request_meta is None:
        return None
    if hasattr(request_meta, "as_dict"):
        return request_meta.as_dict()
    return request_meta if isinstance(request_meta, dict) else None


def _jsonable(value):
    import datetime
    import uuid
    from decimal import Decimal

    if isinstance(value, (datetime.datetime, datetime.date, datetime.time, uuid.UUID)):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value
