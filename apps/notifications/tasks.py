"""Notification + email Celery tasks (docs §12.1). Tasks call services and the
channel layer; no business logic here."""
from __future__ import annotations

from celery import shared_task
from django.utils import timezone


@shared_task
def fanout_notification(notification_id: str):
    """Push a created notification to the recipient's WebSocket group (§12.1)."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from .models import Notification, NotificationDelivery
    from .constants import Channel

    import json
    import redis as sync_redis
    from django.conf import settings

    notif = Notification.objects.filter(id=notification_id).select_related(
        "recipient", "notification_type"
    ).first()
    if notif is None:
        return

    lead_name = ""
    lead_phone = ""
    if notif.related_type == "Lead" and notif.related_id:
        from apps.leads.models import Lead
        lead = Lead.objects.filter(pk=notif.related_id).first()
        if lead:
            lead_name = lead.name
            lead_phone = lead.phone

    payload = {
        "id": str(notif.id),
        "title": notif.title,
        "body": notif.body,
        "code": notif.notification_type.code,
        "type": notif.notification_type.name,
        "priority": notif.priority,
        "related_type": notif.related_type,
        "related_id": notif.related_id,
        "lead_name": lead_name,
        "lead_phone": lead_phone,
        "created_at": notif.created_at.isoformat(),
    }

    # WebSocket delivery via Django Channels layer.
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(
            f"notifications_{notif.recipient_id}",
            {"type": "notify", "payload": payload},
        )

    # SSE delivery via direct Redis pub/sub (more reliable cross-process).
    r = sync_redis.from_url(settings.REDIS_URL)
    r.publish(f"sse_notif:{notif.recipient_id}", str(notif.id))
    r.close()
    NotificationDelivery.objects.filter(
        notification=notif, channel=Channel.WEBSOCKET
    ).update(status="SENT", sent_at=timezone.now())

    # Queue email copies where the delivery policy added an EMAIL channel.
    if NotificationDelivery.objects.filter(
        notification=notif, channel=Channel.EMAIL
    ).exists():
        _queue_email(notif)


def _queue_email(notif):
    if not notif.recipient.email:
        return
    _send_email(notif.recipient.email, notif.title, notif.body)


def _send_email(to_email, subject, body, html=None):
    """Send one email directly over SMTP (no outbox). `body` is the plain-text
    fallback; `html`, when given, is sent as the rich alternative."""
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives

    msg = EmailMultiAlternatives(
        subject=subject, body=body,
        from_email=settings.DEFAULT_FROM_EMAIL, to=[to_email],
    )
    if html:
        msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)


# ─────────────────────── Composite-policy jobs (task 16) ───────────────────────
def _composite_cfg(company, code):
    """Return the policy dict only when enabled, else None."""
    from apps.policies.services import PolicyResolver

    val = PolicyResolver.value(company, code, default=None)
    return val if isinstance(val, dict) and val.get("enabled") else None


@shared_task
def cleanup_old_notifications():
    """Task 16c: delete notifications older than the company's configured age.
    No-op for companies that leave the policy Off."""
    from datetime import timedelta

    from apps.policies.constants import PolicyCode
    from apps.policies.models import CompanyPolicyValue

    from .models import Notification

    now = timezone.now()
    removed = 0
    policy_values = CompanyPolicyValue.objects.filter(
        policy__code=PolicyCode.NOTIFICATION_AUTO_CLEANUP,
        policy__is_active=True
    ).select_related("company")

    for cpv in policy_values:
        cfg = cpv.value_json
        if not cfg or not isinstance(cfg, dict) or not cfg.get("enabled"):
            continue
        days = int(cfg.get("days", 0) or 0)
        if days <= 0:
            continue
        company = cpv.company
        cutoff = now - timedelta(days=days)
        print(f"[Celery notification cleanup] Checking company: {company.name} (ID: {company.id}). Cutoff: {cutoff}")
        deleted, _ = Notification.objects.filter(
            company=company, created_at__lt=cutoff
        ).delete()
        if deleted > 0:
            print(f"[Celery notification cleanup] Deleted {deleted} notifications for company {company.name} older than cutoff {cutoff}")
        removed += deleted
    print(f"[Celery notification cleanup] Completed. Total removed notifications: {removed}")
    return removed


@shared_task
def send_daily_task_emails():
    """Task 16d: email each sales / sales-head their tasks for today (meetings,
    follow-ups, not-reached reminders, leads whose SLA ends today). Skipped on
    the company's configured weekend day(s). No-op when the policy is Off."""
    from apps.policies.constants import PolicyCode
    from apps.policies.models import CompanyPolicyValue
    from apps.accounts.models import User
    from apps.leads.models import FollowUp, Lead, Meeting, Reminder
    from apps.leads.constants import ActiveStatus
    from django.db.models import Q

    now = timezone.localtime()
    today = now.date()
    queued = 0

    policy_values = CompanyPolicyValue.objects.filter(
        policy__code=PolicyCode.DAILY_TASK_EMAIL,
        policy__is_active=True
    ).select_related("company")

    if not policy_values.exists():
        return 0

    company_cfgs = {}
    company_ids = []
    for cpv in policy_values:
        cfg = cpv.value_json
        if not cfg or not isinstance(cfg, dict) or not cfg.get("enabled"):
            continue
        if today.weekday() in {int(d) for d in (cfg.get("weekend_days") or [])}:
            continue
        company_cfgs[cpv.company_id] = cpv.company
        company_ids.append(cpv.company_id)

    if not company_ids:
        return 0

    sales_users = User.objects.filter(
        is_active=True,
        email__isnull=False
    ).filter(
        Q(team_memberships__team__company_id__in=company_ids) |
        Q(headed_teams__company_id__in=company_ids)
    ).distinct().prefetch_related("team_memberships__team", "headed_teams")

    if not sales_users.exists():
        return 0

    user_ids = [u.id for u in sales_users]

    meetings_by_user = {}
    for m in Meeting.objects.filter(assigned_salesman_id__in=user_ids, scheduled_start__date=today, status="SCHEDULED").select_related("lead").order_by("scheduled_start"):
        meetings_by_user.setdefault(m.assigned_salesman_id, []).append(m)

    followups_by_user = {}
    for f in FollowUp.objects.filter(assigned_salesman_id__in=user_ids, scheduled_at__date=today, status="SCHEDULED").select_related("lead").order_by("scheduled_at"):
        followups_by_user.setdefault(f.assigned_salesman_id, []).append(f)

    reminders_by_user = {}
    for r in Reminder.objects.filter(user_id__in=user_ids, reminder_type="STAGE_NOT_REACHED", due_at__date=today, status="PENDING").select_related("lead").order_by("due_at"):
        reminders_by_user.setdefault(r.user_id, []).append(r)

    sla_by_user = {}
    for l in Lead.objects.filter(assigned_salesman_id__in=user_ids, company_id__in=company_ids, active_status=ActiveStatus.ACTIVE, sla_deadline__date=today).order_by("sla_deadline"):
        sla_by_user.setdefault(l.assigned_salesman_id, []).append(l)

    for user in sales_users:
        user_company_ids = set()
        for membership in user.team_memberships.all():
            user_company_ids.add(membership.team.company_id)
        for team in user.headed_teams.all():
            user_company_ids.add(team.company_id)

        for cid in user_company_ids:
            if cid not in company_cfgs:
                continue
            company = company_cfgs[cid]
            
            user_meetings = meetings_by_user.get(user.id, [])
            user_followups = followups_by_user.get(user.id, [])
            user_reminders = reminders_by_user.get(user.id, [])
            user_sla = [l for l in sla_by_user.get(user.id, []) if l.company_id == cid]

            body = _daily_task_email_body_optimized(
                user, today, user_meetings, user_followups, user_reminders, user_sla
            )
            if body is None:
                continue

            html = _daily_task_email_html(
                user, today, user_meetings, user_followups, user_reminders, user_sla
            )
            _send_email(
                user.email,
                f"Your tasks for {today:%a, %d %b %Y}", body, html=html,
            )
            queued += 1
    return queued


def _daily_task_email_body_optimized(user, today, meetings, followups, not_reached, sla_today):
    """Structured plain-text digest. Returns None when the user has nothing
    today (no point emailing an empty list)."""
    if not (meetings or followups or not_reached or sla_today):
        return None

    name = user.get_full_name() or user.email
    lines = [
        f"Hello {name},", "",
        f"Here are your tasks for {today:%A, %d %B %Y}.", "",
    ]

    def section(title, rows):
        lines.append(f"== {title} ({len(rows)}) ==")
        if not rows:
            lines.append("  (none)")
        else:
            lines.extend(rows)
        lines.append("")

    section("Meetings today", [
        f"  - {timezone.localtime(m.scheduled_start):%H:%M} · {m.lead.name} "
        f"({m.lead.phone}){' · ' + m.location if m.location else ''}"
        for m in meetings
    ])
    section("Follow-ups today", [
        f"  - {timezone.localtime(f.scheduled_at):%H:%M} · {f.lead.name} ({f.lead.phone})"
        for f in followups
    ])
    section("Not-reached call reminders", [
        f"  - {timezone.localtime(r.due_at):%H:%M} · "
        f"{r.lead.name if r.lead else 'Lead'}" for r in not_reached
    ])
    section("Leads whose SLA ends today", [
        f"  - {timezone.localtime(l.sla_deadline):%H:%M} · {l.name} ({l.phone})"
        for l in sla_today
    ])

    lines.append("— Argoz CRM")
    return "\n".join(lines)


def _daily_task_email_html(user, today, meetings, followups, not_reached, sla_today):
    """Inline-styled HTML digest (email clients ignore <style>, so styles are
    inline). Mirrors the plain-text sections. Returns None when empty."""
    from html import escape

    if not (meetings or followups or not_reached or sla_today):
        return None

    name = escape(user.get_full_name() or user.email)
    accent = {"meet": "#2563eb", "follow": "#0891b2",
              "reach": "#d97706", "sla": "#dc2626"}

    def row(time_str, primary, secondary=""):
        sec = f'<span style="color:#6b7280">{escape(secondary)}</span>' if secondary else ""
        return (
            '<tr>'
            f'<td style="padding:8px 12px;font-weight:600;color:#111827;white-space:nowrap">{escape(time_str)}</td>'
            f'<td style="padding:8px 12px;color:#374151">{escape(primary)} {sec}</td>'
            '</tr>'
        )

    def section(title, color, rows):
        if not rows:
            return ""
        body = "".join(rows)
        return (
            f'<tr><td colspan="2" style="padding:18px 12px 6px">'
            f'<span style="display:inline-block;background:{color};color:#fff;'
            f'font-size:13px;font-weight:600;padding:4px 10px;border-radius:12px">'
            f'{escape(title)} · {len(rows)}</span></td></tr>'
            f'{body}'
        )

    sections = (
        section("Meetings", accent["meet"], [
            row(f"{timezone.localtime(m.scheduled_start):%H:%M}", m.lead.name,
                f"{m.lead.phone}" + (f" · {m.location}" if m.location else ""))
            for m in meetings
        ])
        + section("Follow-ups", accent["follow"], [
            row(f"{timezone.localtime(f.scheduled_at):%H:%M}", f.lead.name, f.lead.phone)
            for f in followups
        ])
        + section("Not-reached call reminders", accent["reach"], [
            row(f"{timezone.localtime(r.due_at):%H:%M}",
                r.lead.name if r.lead else "Lead")
            for r in not_reached
        ])
        + section("SLA ends today", accent["sla"], [
            row(f"{timezone.localtime(l.sla_deadline):%H:%M}", l.name, l.phone)
            for l in sla_today
        ])
    )

    return f"""\
<div style="background:#f3f4f6;padding:24px 0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0"
             style="max-width:600px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)">
        <tr><td style="background:#111827;padding:20px 24px">
          <span style="color:#fff;font-size:18px;font-weight:700">Argoz CRM</span>
          <span style="color:#9ca3af;font-size:14px;float:right">{today:%a, %d %b %Y}</span>
        </td></tr>
        <tr><td style="padding:24px 24px 4px">
          <p style="margin:0;font-size:16px;color:#111827">Hello {name},</p>
          <p style="margin:6px 0 0;font-size:14px;color:#6b7280">Here are your tasks for today.</p>
        </td></tr>
        <tr><td style="padding:0 12px 16px">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="font-size:14px;border-collapse:collapse">{sections}</table>
        </td></tr>
        <tr><td style="padding:16px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px">
          — Argoz CRM · automated daily digest
        </td></tr>
      </table>
    </td></tr>
  </table>
</div>"""
