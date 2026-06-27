"""Leads analysis report aggregation (docs §14, §15.1). Read-only company-wide
pipeline analytics: stage distribution, source-channel performance, origin
split, active/inactive split and the daily generation/conversion timeline.

Access is gated by the ``review_leads_analysis`` permission; the figures are
company-wide (no per-team scoping). The view/API stay thin and call ``build``
here — no business logic in the view."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from ..constants import ActiveStatus, Origin, StageCode
from ..models import Lead, LeadStageHistory

# Stages shown on the report, in pipeline order (presentation lives in the JS).
_STAGES = [
    StageCode.FRESH, StageCode.FOLLOW_UP, StageCode.NOT_REACHED,
    StageCode.MEETING, StageCode.INTERESTED, StageCode.FROZEN,
]
_TIMELINE_DAYS = 14


class LeadsAnalysisService:
    @staticmethod
    def build(company) -> dict:
        leads = Lead.objects.filter(company=company)
        return {
            "stageCounts": LeadsAnalysisService._stage_counts(leads),
            "sources": LeadsAnalysisService._sources(leads),
            "sourceStages": LeadsAnalysisService._source_stages(leads),
            "timeline": LeadsAnalysisService._timeline(company),
            "activeTotal": leads.filter(active_status=ActiveStatus.ACTIVE).count(),
            "inactiveTotal": leads.filter(active_status=ActiveStatus.INACTIVE).count(),
            "todayNew": leads.filter(
                created_at__date=timezone.localdate()
            ).count(),
        }

    @staticmethod
    def _stage_counts(leads) -> dict:
        rows = leads.values("current_stage__code").annotate(c=Count("id"))
        counts = {r["current_stage__code"]: r["c"] for r in rows}
        return {code: counts.get(code, 0) for code in _STAGES}

    @staticmethod
    def _sources(leads) -> list[dict]:
        rows = leads.values("source__code", "source__name").annotate(
            count=Count("id"),
            interested=Count("id", filter=Q(current_stage__code=StageCode.INTERESTED)),
        ).order_by("-count")
        # Dominant origin per source (each source row carries one origin for the
        # origin split/donut, mirroring the static contract).
        origin_rows = leads.values("source__code", "origin").annotate(c=Count("id"))
        broker, total = {}, {}
        for r in origin_rows:
            code = r["source__code"]
            total[code] = total.get(code, 0) + r["c"]
            if r["origin"] == Origin.BROKER:
                broker[code] = broker.get(code, 0) + r["c"]
        out = []
        for r in rows:
            code = r["source__code"]
            if not code:
                continue
            is_broker = broker.get(code, 0) * 2 > total.get(code, 0)
            out.append({
                "source": code,
                "label": r["source__name"] or code,
                "origin": Origin.BROKER if is_broker else Origin.DIRECT,
                "count": r["count"],
                "interested": r["interested"],
            })
        return out

    @staticmethod
    def _source_stages(leads) -> dict:
        rows = leads.values("source__code", "current_stage__code").annotate(
            c=Count("id")
        )
        out: dict = {}
        for r in rows:
            code = r["source__code"]
            stage = r["current_stage__code"]
            if not code or stage not in _STAGES:
                continue
            out.setdefault(code, {})[stage] = r["c"]
        return out

    @staticmethod
    def _timeline(company) -> list[dict]:
        start = timezone.localdate() - timedelta(days=_TIMELINE_DAYS - 1)
        created = {
            r["d"]: r["c"]
            for r in Lead.objects.filter(
                company=company, created_at__date__gte=start
            ).annotate(d=TruncDate("created_at")).values("d").annotate(c=Count("id"))
        }
        converted = {
            r["d"]: r["c"]
            for r in LeadStageHistory.objects.filter(
                lead__company=company, to_stage__code=StageCode.INTERESTED,
                changed_at__date__gte=start,
            ).annotate(d=TruncDate("changed_at")).values("d").annotate(c=Count("id"))
        }
        out = []
        for i in range(_TIMELINE_DAYS):
            day = start + timedelta(days=i)
            out.append({
                "date": day.strftime("%b %d"),
                "created": created.get(day, 0),
                "converted": converted.get(day, 0),
            })
        return out
