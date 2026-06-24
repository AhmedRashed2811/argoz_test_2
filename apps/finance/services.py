"""Finance approval façade (docs §3: finance owns approval screens, not campaign
creation). Delegates the write to CampaignApprovalService so budget rules and
audit stay centralized in marketing. Read serialization for the approval queue
also lives here so views stay thin (§10.3, §14)."""
from __future__ import annotations

from django.utils import timezone

from apps.marketing.constants import ApprovalStatus
from apps.marketing.models import Campaign, CampaignApprovalHistory, Project
from apps.marketing.services import CampaignApprovalService

# JS approval tokens <-> persisted statuses (the static finance page uses these).
_JS_TO_STATUS = {
    "pending": ApprovalStatus.PENDING, "approved": ApprovalStatus.APPROVED,
    "semi": ApprovalStatus.SEMI_APPROVED, "not-approved": ApprovalStatus.NOT_APPROVED,
}
_STATUS_TO_JS = {v: k for k, v in _JS_TO_STATUS.items()}
_TYPE_LABELS = {
    "EVENTS": "Events", "TV_ADS": "TV Ads", "STREET_ADS": "Street Ads",
    "SOCIAL_MEDIA": "Social Media", "EXHIBITION": "Exhibition",
}
_HISTORY_ACTION = {
    ApprovalStatus.APPROVED: "Approved Campaign Budget",
    ApprovalStatus.SEMI_APPROVED: "Semi-Approved Campaign Budget",
    ApprovalStatus.NOT_APPROVED: "Rejected Campaign Budget",
    ApprovalStatus.PENDING: "Reset to Pending",
}


def _initials(name):
    parts = (name or "").split()
    return ("".join(p[0] for p in parts[:2]) or "—").upper()


class FinanceApprovalService:
    @staticmethod
    def approve(*, campaign_id, actor, reason="", request_meta=None):
        return CampaignApprovalService.set_status(
            campaign_id=campaign_id, status=ApprovalStatus.APPROVED, actor=actor,
            reason=reason, request_meta=request_meta,
        )

    @staticmethod
    def semi_approve(*, campaign_id, actor, reason, request_meta=None):
        return CampaignApprovalService.set_status(
            campaign_id=campaign_id, status=ApprovalStatus.SEMI_APPROVED, actor=actor,
            reason=reason, request_meta=request_meta,
        )

    @staticmethod
    def reject(*, campaign_id, actor, reason, request_meta=None):
        return CampaignApprovalService.set_status(
            campaign_id=campaign_id, status=ApprovalStatus.NOT_APPROVED, actor=actor,
            reason=reason, request_meta=request_meta,
        )

    @staticmethod
    def decide(*, campaign_id, js_status, actor, reason="", request_meta=None):
        """Map the page's approval token to a persisted status and record it.
        All rules/audit/notify stay in CampaignApprovalService."""
        status = _JS_TO_STATUS.get(js_status)
        if status is None:
            from apps.core.exceptions import ValidationError
            raise ValidationError(f"Unknown approval action: {js_status}")
        return CampaignApprovalService.set_status(
            campaign_id=campaign_id, status=status, actor=actor,
            reason=reason or "", request_meta=request_meta,
        )

    # ── read side: serialize the queue for the finance page ───────────────
    @staticmethod
    def queue_payload(company) -> dict:
        campaigns = (
            Campaign.objects.filter(company=company, archived_at__isnull=True)
            .select_related("created_by")
            .prefetch_related(
                "selected_types", "approval_history__actor", "other_costs",
                "events__celebrities", "events__giveaways", "events__catering",
                "tv_ads__channels", "street_ads__type_lines__ad_type",
                "street_ads__type_lines__locations",
                "social_ads__platform_lines__platform",
                "exhibitions",
            )
            .order_by("-created_at")
        )
        projects = {p.id: p.name for p in Project.objects.filter(company=company)}
        today = timezone.localdate()
        history_today = CampaignApprovalHistory.objects.filter(
            campaign__company=company, created_at__date=today
        )
        return {
            "campaigns": [FinanceApprovalService._serialize(c, projects) for c in campaigns],
            "kpis": {
                "approvedToday": history_today.filter(to_status=ApprovalStatus.APPROVED).count(),
                "rejectedToday": history_today.filter(to_status=ApprovalStatus.NOT_APPROVED).count(),
            },
        }

    @staticmethod
    def _serialize(c, projects):
        return {
            "id": str(c.id),
            "name": c.name,
            "types": [_TYPE_LABELS.get(t.type_code, t.type_code) for t in c.selected_types.all()],
            "submittedBy": (c.created_by.get_full_name() or c.created_by.get_username()
                            if c.created_by else "—"),
            "submittedDate": c.created_at.date().isoformat(),
            "approval": _STATUS_TO_JS.get(c.approval_status, "pending"),
            "budget": float(c.total_budget),
            "target": (f"Project — {projects[c.target_id]}"
                       if c.target_type == "PROJECT" and c.target_id in projects else "—"),
            "dateRange": f"{c.start_date:%d %b %Y} – {c.end_date:%d %b %Y}",
            "budgetBreakdown": FinanceApprovalService._breakdown(c),
            "history": FinanceApprovalService._history(c),
        }

    @staticmethod
    def _breakdown(c):
        sections = []

        def section(label, items, subtotal):
            if items:
                sections.append({"type": label, "items": items, "subtotal": float(subtotal)})

        ev_items, ev_total = [], 0
        for ev in c.events.all():
            ev_items.append({"label": ev.name or "Event", "amount": float(ev.budget)})
            ev_total += float(ev.budget)
            for cel in ev.celebrities.all():
                ev_items.append({"label": f"↳ Celebrity: {cel.name}", "amount": float(cel.budget)})
                ev_total += float(cel.budget)
            for gv in ev.giveaways.all():
                ev_items.append({"label": f"↳ Giveaway: {gv.name}", "amount": float(gv.budget)})
                ev_total += float(gv.budget)
            for ct in ev.catering.all():
                ev_items.append({"label": f"↳ Catering: {ct.name}", "amount": float(ct.budget)})
                ev_total += float(ct.budget)
        section("Events", ev_items, ev_total)

        tv_items, tv_total = [], 0
        for tv in c.tv_ads.all():
            tv_items.append({"label": tv.name or "TV Ad", "amount": float(tv.budget)})
            tv_total += float(tv.budget)
            for ch in tv.channels.all():
                tv_items.append({"label": f"↳ Channel: {ch.channel_name}", "amount": float(ch.budget)})
                tv_total += float(ch.budget)
        section("TV Ads", tv_items, tv_total)

        st_items, st_total = [], 0
        for st in c.street_ads.all():
            st_items.append({"label": st.name or "Street Ad", "amount": float(st.budget)})
            st_total += float(st.budget)
            for line in st.type_lines.all():
                st_items.append({"label": f"↳ {line.ad_type.name}", "amount": float(line.budget)})
                st_total += float(line.budget)
                for loc in line.locations.all():
                    st_items.append({"label": f"↳ {loc.location_text}", "amount": float(loc.budget)})
                    st_total += float(loc.budget)
        section("Street Ads", st_items, st_total)

        sm_items, sm_total = [], 0
        for sm in c.social_ads.all():
            ad_total = sum(float(p.budget) for p in sm.platform_lines.all())
            sm_items.append({"label": sm.name or "Social Ad", "amount": ad_total})
            for p in sm.platform_lines.all():
                sm_items.append({"label": f"↳ {p.platform.name}", "amount": float(p.budget)})
            sm_total += ad_total
        section("Social Media", sm_items, sm_total)

        ex_items, ex_total = [], 0
        for ex in c.exhibitions.all():
            ex_items.append({"label": ex.name or "Exhibition", "amount": float(ex.budget)})
            ex_total += float(ex.budget)
        section("Exhibition", ex_items, ex_total)

        oc_items, oc_total = [], 0
        for oc in c.other_costs.all():
            oc_items.append({"label": oc.reason or "Other", "amount": float(oc.value)})
            oc_total += float(oc.value)
        section("Other Costs", oc_items, oc_total)

        return sections

    @staticmethod
    def _history(c):
        out = []
        for h in c.approval_history.all().order_by("created_at"):
            name = (h.actor.get_full_name() or h.actor.get_username()) if h.actor else "System"
            out.append({
                "user": _initials(name), "name": name,
                "action": _HISTORY_ACTION.get(h.to_status, "Updated Approval"),
                "date": timezone.localtime(h.created_at).strftime("%b %d, %Y — %I:%M %p"),
                "status": _STATUS_TO_JS.get(h.to_status, "pending"),
                "note": h.reason or None,
            })
        return out
