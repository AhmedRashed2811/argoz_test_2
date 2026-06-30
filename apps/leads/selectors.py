"""Lead read queries (docs §15.1 selectors). Thin wrappers that apply
company/user scope and eager-load relations to keep views query-efficient."""
from __future__ import annotations

from django.utils import timezone

from .constants import ActiveStatus, SLAStatus
from .models import FollowUp, Lead, Meeting, Reminder, SLAInstance


def lead_detail_qs():
    """Fully-loaded lead queryset for detail views and services that need
    related objects without additional queries."""
    return Lead.objects.select_related(
        "company", "source", "current_stage", "language",
        "assigned_salesman", "assigned_team",
        "broker_owner", "campaign", "created_by",
    ).prefetch_related(
        "followups__assigned_salesman",
        "meetings__assigned_salesman",
        "lead_notes__created_by",
        "activities__actor",
        "stage_history__from_stage",
        "stage_history__to_stage",
        "stage_history__actor",
        "assignment_history__to_salesman",
        "assignment_history__from_salesman",
        "assignment_history__to_team",
        "assignment_history__from_team",
        "assignment_history__actor",
        "broker_ownership_history__broker",
    )


def active_leads_for_salesman(user, company):
    return Lead.objects.filter(
        company=company,
        assigned_salesman=user,
        active_status=ActiveStatus.ACTIVE,
    ).select_related("source", "current_stage", "campaign")


def leads_with_active_sla(company):
    """All active leads that have an active SLA (used for monitoring)."""
    return Lead.objects.filter(
        company=company,
        active_status=ActiveStatus.ACTIVE,
        sla_instances__status=SLAStatus.ACTIVE,
    ).select_related("assigned_salesman", "assigned_team", "current_stage").distinct()


def due_reminders(company=None):
    now = timezone.now()
    qs = Reminder.objects.select_related("lead", "lead__company", "user").filter(
        status="PENDING", due_at__lte=now
    )
    if company is not None:
        qs = qs.filter(company=company)
    return qs


def pending_followups(user, company):
    return FollowUp.objects.filter(
        assigned_salesman=user,
        lead__company=company,
        status="SCHEDULED",
    ).select_related("lead", "lead__current_stage").order_by("scheduled_at")


def pending_meetings(user, company):
    return Meeting.objects.filter(
        assigned_salesman=user,
        lead__company=company,
        status="SCHEDULED",
    ).select_related("lead", "lead__current_stage").order_by("scheduled_start")


def expired_sla_instances(now, company=None, limit=100):
    """Expired active SLA instances for the SLA job (use locks.expired_sla_batch
    in Celery tasks for skip_locked behaviour)."""
    qs = SLAInstance.objects.select_related(
        "lead", "lead__company", "lead__assigned_salesman"
    ).filter(status=SLAStatus.ACTIVE, deadline_at__lte=now)
    if company is not None:
        qs = qs.filter(lead__company=company)
    return qs.order_by("deadline_at")[:limit]


def _cal_event(kind, dt, lead, salesman=None, extra=None):
    """Shape one calendar event. `date`/`time` are in server-local time so the
    client groups into day cells without timezone drift."""
    local = timezone.localtime(dt)
    return {
        "type": kind,
        "start": dt.isoformat(),
        "date": local.strftime("%Y-%m-%d"),
        "time": local.strftime("%H:%M"),
        "lead_id": str(lead.id),
        "lead_name": lead.name,
        "lead_phone": lead.phone,
        "stage": lead.current_stage.name if lead.current_stage else "",
        "salesman": (salesman.get_full_name() or salesman.email) if salesman else "",
        "extra": extra or {},
    }


def calendar_events(user, company, start, end):
    """Scoped, forward-looking calendar events between [max(start, now), end):
    upcoming follow-ups, meetings, active SLA deadlines and freeze returns for
    the user's own/team/all active leads. Excludes inactive leads, expired or
    breached SLAs, and anything in the past. Scope reuses leads_for_user."""
    from apps.reports.selectors import leads_for_user

    lead_ids = list(
        leads_for_user(user, company)
        .filter(active_status=ActiveStatus.ACTIVE)
        .values_list("id", flat=True)
    )
    events: list[dict] = []
    if not lead_ids:
        return events

    # Never surface past events — clamp the window's lower bound to now.
    lower = max(start, timezone.now())

    for f in FollowUp.objects.filter(
        lead_id__in=lead_ids, status="SCHEDULED",
        scheduled_at__gte=lower, scheduled_at__lt=end,
    ).select_related("lead", "lead__current_stage", "assigned_salesman"):
        events.append(_cal_event("followup", f.scheduled_at, f.lead,
                                  salesman=f.assigned_salesman,
                                  extra={"notes": f.notes}))

    for m in Meeting.objects.filter(
        lead_id__in=lead_ids, status="SCHEDULED",
        scheduled_start__gte=lower, scheduled_start__lt=end,
    ).select_related("lead", "lead__current_stage", "assigned_salesman"):
        events.append(_cal_event("meeting", m.scheduled_start, m.lead,
                                 salesman=m.assigned_salesman,
                                 extra={"location": m.location}))

    # Active SLAs only with a future deadline — breached/expired are excluded.
    for s in SLAInstance.objects.filter(
        lead_id__in=lead_ids, status=SLAStatus.ACTIVE,
        deadline_at__gte=lower, deadline_at__lt=end,
    ).select_related("lead", "lead__current_stage", "stage", "assigned_salesman"):
        events.append(_cal_event("sla", s.deadline_at, s.lead,
                                 salesman=s.assigned_salesman,
                                 extra={"stage": s.stage.name if s.stage else ""}))

    for r in Reminder.objects.filter(
        lead_id__in=lead_ids, reminder_type="FROZEN_RETURN",
        due_at__gte=lower, due_at__lt=end,
    ).select_related("lead", "lead__current_stage", "user"):
        events.append(_cal_event("freeze", r.due_at, r.lead,
                                 salesman=r.user, extra={"status": r.status}))

    events.sort(key=lambda e: e["start"])
    return events


def existing_client(company, phone):
    """The Client row for a phone in this company, salesman eager-loaded."""
    from .models import Client

    phone = (phone or "").strip()
    if not phone:
        return None
    return (
        Client.objects.filter(company=company, phone=phone)
        .select_related("original_salesman").first()
    )


def active_brokers(company):
    from apps.accounts.models import Broker, BrokerStatus

    return Broker.objects.filter(
        company=company, status=BrokerStatus.ACTIVE
    ).order_by("name")


def active_teams(company):
    from apps.accounts.models import Team

    return Team.objects.filter(
        company=company, is_active=True
    ).order_by("order_index", "name")


def head_team_members(user, company):
    """Active members of the team(s) the user is sales head of."""
    from apps.accounts.models import Team

    teams = Team.objects.filter(company=company, sales_head=user)
    return [m for t in teams for m in t.members.select_related("user", "team")
            if m.user.is_active]


def call_center_agents(company):
    """Users in the CALL_CENTER role for this company (§4.2g)."""
    from apps.accounts.models import User
    from apps.authorization.services import RoleService

    users = User.objects.filter(
        is_active=True, profile__company=company
    ).select_related("profile")
    return [u for u in users
            if RoleService.CALL_CENTER_CODE in RoleService.role_codes(u)]


def leads_list_for_user(user, company, search_q="") -> list[Lead]:
    from apps.reports.selectors import leads_for_user
    import uuid
    from django.db.models import Q

    qs = leads_for_user(user, company)
    search_q = (search_q or "").strip()
    if search_q:
        try:
            val = uuid.UUID(search_q)
            qs = qs.filter(id=val)
        except ValueError:
            qs = qs.filter(Q(name__icontains=search_q) | Q(phone__icontains=search_q))
    return qs[:200]

