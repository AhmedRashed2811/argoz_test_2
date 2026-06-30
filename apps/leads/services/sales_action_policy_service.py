"""Enforcement for the per-lead sales-action policies (task 16a/16b).

Only sales and sales-heads are constrained; sales operations (and superusers)
act without restriction. Both policies are On/Off and default Off, so when
disabled or unconfigured these checks are no-ops.

Action counts are per (lead, salesman): a lead reassigned to a different
salesman gives the new salesman a zero count automatically.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.core.exceptions import ValidationError
from apps.policies.constants import PolicyCode
from apps.policies.services import PolicyResolver

from ..constants import StageCode

_RESTRICTED_ROLES = {"SALES", "SALES_HEAD"}


def _is_restricted(actor) -> bool:
    """True only for sales / sales-head actors (operations are unrestricted)."""
    if actor is None or getattr(actor, "is_superuser", False):
        return False
    from apps.authorization.services import RoleService
    codes = set(RoleService.role_codes(actor))
    if "SALES_OPERATION" in codes:
        return False
    return bool(codes & _RESTRICTED_ROLES)


def _composite(company, code):
    val = PolicyResolver.value(company, code, default=None)
    if isinstance(val, dict) and val.get("enabled"):
        return val
    return None


def enforce_action_limit(*, lead, salesman, actor, action: str) -> None:
    """Block a meeting/follow-up/freeze that would exceed the configured per-lead
    cap for this salesman. `action` is 'meeting' | 'followup' | 'freeze'."""
    if not _is_restricted(actor) or salesman is None:
        return
    cfg = _composite(lead.company, PolicyCode.SALES_ACTION_LIMITS)
    if not cfg:
        return
    if action == "meeting":
        cap = int(cfg.get("max_meetings", 0) or 0)
        done = lead.meetings.filter(assigned_salesman=salesman).count()
        noun = "meetings"
    elif action == "followup":
        cap = int(cfg.get("max_followups", 0) or 0)
        done = lead.followups.filter(assigned_salesman=salesman).count()
        noun = "follow-ups"
    elif action == "freeze":
        cap = int(cfg.get("max_freezes", 0) or 0)
        done = lead.stage_history.filter(
            to_stage__code=StageCode.FROZEN, actor=salesman).count()
        noun = "freezes"
    else:
        return
    if cap and done >= cap:
        raise ValidationError(
            f"Policy limit reached: you may only do {cap} {noun} for this lead.")


_STAGE_CAPACITY_KEY = {
    StageCode.MEETING: "max_meeting",
    StageCode.FOLLOW_UP: "max_followup",
    StageCode.FROZEN: "max_freeze",
}


def enforce_stage_capacity(*, lead, salesman, actor, to_stage_code: str) -> None:
    """Block moving a lead into Meeting/Follow-up/Frozen when the salesman is
    already at the configured cap of leads in that stage (task 1a). Off by
    default and a no-op for non-restricted actors / unconfigured caps."""
    key = _STAGE_CAPACITY_KEY.get(to_stage_code)
    if key is None or not _is_restricted(actor) or salesman is None:
        return
    cfg = _composite(lead.company, PolicyCode.SALES_STAGE_CAPACITY)
    if not cfg:
        return
    cap = int(cfg.get(key, 0) or 0)
    if not cap:
        return
    from ..constants import ActiveStatus

    current = (
        type(lead).objects.filter(
            company=lead.company, assigned_salesman=salesman,
            current_stage__code=to_stage_code, active_status=ActiveStatus.ACTIVE,
        ).exclude(id=lead.id).count()
    )
    if current >= cap:
        noun = to_stage_code.replace("_", " ").title()
        raise ValidationError(
            f"Policy limit reached: you may hold at most {cap} lead(s) in the "
            f"{noun} stage. Resolve an existing one first.")


def enforce_max_duration(*, company, actor, action: str, scheduled_at=None,
                         days: int | None = None) -> None:
    """Block scheduling further ahead than the configured cap. For meetings/
    follow-ups pass `scheduled_at`; for freeze pass `days`."""
    if not _is_restricted(actor):
        return
    cfg = _composite(company, PolicyCode.SALES_ACTION_MAX_DURATION)
    if not cfg:
        return
    key = {"meeting": "meeting_days", "followup": "followup_days",
           "freeze": "freeze_days"}.get(action)
    max_days = int(cfg.get(key, 0) or 0)
    if not max_days:
        return
    if action == "freeze":
        if days is not None and days > max_days:
            raise ValidationError(
                f"Policy limit: a freeze may last at most {max_days} day(s).")
        return
    if scheduled_at is not None:
        horizon = timezone.now() + timedelta(days=max_days)
        if scheduled_at > horizon:
            raise ValidationError(
                f"Policy limit: a {action} can be at most {max_days} day(s) ahead.")
