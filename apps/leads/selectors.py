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

