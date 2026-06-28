"""Composite On/Off policy schemas (task 16).

Each composite policy stores a single dict in CompanyPolicyValue.value_json:
    {"enabled": bool, <field_key>: <value>, ...}

The schema below is the single source of truth shared by:
  * the policy-edit template (renders a toggle + the fields),
  * set_value_from_post (parses the posted fields back into the dict),
  * the services that enforce the policy (read fields via PolicyResolver).

Field types:
  int      -> non-negative whole number
  weekdays -> list[int] of weekday numbers (0=Mon … 6=Sun)
"""
from __future__ import annotations

from .constants import PolicyCode

WEEKDAY_CHOICES = [
    (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
    (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
]

COMPOSITE_SCHEMA: dict[str, dict] = {
    PolicyCode.SALES_ACTION_LIMITS: {
        "toggle_label": "Enforce a maximum number of meetings, follow-ups and "
                        "freezes a sales/sales-head may do for one lead",
        "note": "Counts reset automatically when a lead is reassigned to a "
                "different salesman (the new salesman starts at zero). Sales "
                "operations are never restricted.",
        "fields": [
            {"key": "max_meetings", "label": "Max meetings per lead", "type": "int", "default": 1},
            {"key": "max_followups", "label": "Max follow-ups per lead", "type": "int", "default": 1},
            {"key": "max_freezes", "label": "Max freezes per lead", "type": "int", "default": 1},
        ],
    },
    PolicyCode.SALES_ACTION_MAX_DURATION: {
        "toggle_label": "Cap how far ahead a sales/sales-head may schedule a "
                        "meeting or follow-up, and the maximum freeze length",
        "note": "Values are in days. Sales operations are never restricted.",
        "fields": [
            {"key": "meeting_days", "label": "Max days ahead for a meeting", "type": "int", "default": 10},
            {"key": "followup_days", "label": "Max days ahead for a follow-up", "type": "int", "default": 10},
            {"key": "freeze_days", "label": "Max freeze length (days)", "type": "int", "default": 10},
        ],
    },
    PolicyCode.NOTIFICATION_AUTO_CLEANUP: {
        "toggle_label": "Automatically delete old notifications",
        "note": "A background job removes notifications older than the chosen age.",
        "fields": [
            {"key": "days", "label": "Delete notifications older than (days)", "type": "int", "default": 10},
        ],
    },
    PolicyCode.DAILY_TASK_EMAIL: {
        "toggle_label": "Email every sales/sales-head their tasks for the day",
        "note": "A daily email lists today's meetings, follow-ups, not-reached "
                "reminders and leads whose SLA ends today. Skipped on the "
                "selected weekend day(s).",
        "fields": [
            {"key": "weekend_days", "label": "Weekend day(s) — no email sent", "type": "weekdays", "default": [4, 5]},
        ],
    },
    PolicyCode.WEEKEND_SLA_FREEZE: {
        "toggle_label": "Freeze SLA remaining time on weekend day(s)",
        "note": "Weekend day(s) are not counted against the SLA of active "
                "assigned leads.",
        "fields": [
            {"key": "weekend_days", "label": "Weekend day(s)", "type": "weekdays", "default": [4, 5]},
        ],
    },
}


def default_value(code: str) -> dict:
    """The default (disabled) dict for a composite policy."""
    schema = COMPOSITE_SCHEMA[code]
    out = {"enabled": False}
    for f in schema["fields"]:
        out[f["key"]] = f["default"]
    return out


def parse_post(code: str, data: dict) -> dict:
    """Build the value_json dict from posted fields, coercing per field type."""
    schema = COMPOSITE_SCHEMA[code]
    out = {"enabled": bool(data.get("enabled"))}
    for f in schema["fields"]:
        raw = data.get(f["key"])
        if f["type"] == "int":
            out[f["key"]] = max(0, int(raw or 0))
        elif f["type"] == "weekdays":
            days = raw if isinstance(raw, list) else []
            out[f["key"]] = sorted({int(d) for d in days if str(d).strip() != ""})
        else:
            out[f["key"]] = raw
    return out


def schema_for_template(code: str, value_json: dict | None) -> dict | None:
    """Schema enriched with current values, ready for the edit template."""
    if code not in COMPOSITE_SCHEMA:
        return None
    schema = COMPOSITE_SCHEMA[code]
    current = value_json if isinstance(value_json, dict) else default_value(code)
    fields = []
    for f in schema["fields"]:
        val = current.get(f["key"], f["default"])
        entry = {**f, "value": val}
        if f["type"] == "weekdays":
            sel = set(val or [])
            entry["choices"] = [
                {"num": n, "name": name, "selected": n in sel}
                for n, name in WEEKDAY_CHOICES
            ]
        fields.append(entry)
    return {
        "toggle_label": schema["toggle_label"],
        "note": schema.get("note", ""),
        "enabled": bool(current.get("enabled", False)),
        "fields": fields,
    }
