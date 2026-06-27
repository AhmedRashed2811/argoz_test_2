"""Sales performance report aggregation (docs §14, §15.1). Read-only: rolls up
per-salesperson conversion, SLA compliance, response time, per-team SLA breach
detail and the pipeline funnel.

Scope (security): a Sales Head sees only the team(s) they head; holders with
``leads.lead.view_all`` (and other privileged report roles) see every team. The
view/API stay thin and call ``build`` here — no business logic in the view."""
from __future__ import annotations

from django.db.models import Prefetch

from apps.accounts.models import Team
from apps.authorization.services import EffectivePermissionResolver

from ..constants import SLAStatus, StageCode
from ..models import Lead, LeadStageHistory, SLAInstance

# SLA instances that represent a settled outcome: COMPLETED = the owner acted in
# time, BREACHED = the SLA expired and the lead was redistributed. ACTIVE (still
# running) and CANCELLED (lead deactivated / moved by admin) are not compliance
# signals.
_SETTLED_SLA = (SLAStatus.COMPLETED, SLAStatus.BREACHED)


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


def _new_sales_agg():
    return {"assigned": 0, "interested": 0, "sla_total": 0, "sla_met": 0,
            "resp_sum": 0.0, "resp_n": 0, "vel_sum": 0.0, "vel_n": 0}


class SalesPerformanceService:
    @staticmethod
    def visible_teams(user, company):
        """Teams the user may see on the report. Sales Head -> only headed
        teams; view_all (Directors, etc.) and the other report roles -> all."""
        teams = Team.objects.filter(company=company, is_active=True)
        if EffectivePermissionResolver.has(user, "leads.lead.view_all"):
            return teams
        headed = teams.filter(sales_head=user)
        if headed.exists():
            return headed
        return teams

    @staticmethod
    def build(user, company) -> dict:
        teams = list(SalesPerformanceService.visible_teams(user, company))
        team_ids = [t.id for t in teams]
        team_names = {t.id: t.name for t in teams}

        leads = Lead.objects.filter(
            company=company, assigned_team_id__in=team_ids
        ).select_related("assigned_salesman", "current_stage").prefetch_related(
            Prefetch("stage_history",
                     queryset=LeadStageHistory.objects.select_related("to_stage")
                     .order_by("changed_at"))
        )

        funnel_counts: dict = {}
        sales: dict = {}        # salesman_id -> aggregate
        sales_meta: dict = {}   # salesman_id -> (name, team_id)

        for lead in leads:
            code = lead.current_stage.code if lead.current_stage_id else StageCode.FRESH
            funnel_counts[code] = funnel_counts.get(code, 0) + 1

            history = list(lead.stage_history.all())
            first_response = history[0].changed_at if history else None
            # Lifecycle velocity: time from creation to reaching Interested.
            interested_at = next(
                (h.changed_at for h in history
                 if h.to_stage_id and h.to_stage.code == StageCode.INTERESTED),
                None,
            )

            sid = lead.assigned_salesman_id
            if not sid:
                continue
            agg = sales.setdefault(sid, _new_sales_agg())
            sm = lead.assigned_salesman
            sales_meta[sid] = (sm.get_full_name() or sm.email, lead.assigned_team_id)
            agg["assigned"] += 1
            if code == StageCode.INTERESTED:
                agg["interested"] += 1
            if first_response:
                agg["resp_sum"] += (
                    first_response - lead.created_at
                ).total_seconds() / 60.0
                agg["resp_n"] += 1
            if interested_at:
                agg["vel_sum"] += (
                    interested_at - lead.created_at
                ).total_seconds() / 3600.0
                agg["vel_n"] += 1

        # SLA compliance measured per lead: did the lead's FIRST SLA window get
        # met? Redistribution churn (one lead breaching repeatedly) is ignored —
        # only the first owner's window counts, attributed to that owner and the
        # lead's team. One instance per lead -> stable, comparable rates.
        team_sla = {tid: {"total": 0, "breached": 0} for tid in team_ids}
        seen_leads: set = set()
        sla_rows = SLAInstance.objects.filter(
            lead__company=company, lead__assigned_team_id__in=team_ids,
            assigned_salesman__isnull=False, status__in=_SETTLED_SLA,
        ).order_by("lead_id", "start_at").values_list(
            "lead_id", "assigned_salesman_id", "lead__assigned_team_id", "status"
        )
        for lead_id, sid, team_id, status in sla_rows:
            if lead_id in seen_leads:   # only the lead's first settled window
                continue
            seen_leads.add(lead_id)
            breached = status == SLAStatus.BREACHED
            if team_id in team_sla:
                team_sla[team_id]["total"] += 1
                if breached:
                    team_sla[team_id]["breached"] += 1
            agg = sales.get(sid)
            if agg is not None:
                agg["sla_total"] += 1
                if not breached:
                    agg["sla_met"] += 1

        return {
            "sales": SalesPerformanceService._sales_rows(sales, sales_meta),
            "teams": SalesPerformanceService._team_rows(teams, team_names, team_sla),
            "funnel": SalesPerformanceService._funnel(funnel_counts),
        }

    @staticmethod
    def _sales_rows(sales, sales_meta) -> list[dict]:
        out = []
        for sid, agg in sales.items():
            name, team_id = sales_meta[sid]
            assigned = agg["assigned"]
            out.append({
                "id": str(sid),
                "name": name,
                "initials": _initials(name),
                "team": str(team_id),
                "assigned": assigned,
                "interested": agg["interested"],
                "conv": round(agg["interested"] / assigned * 100, 1) if assigned else 0,
                "sla": round(agg["sla_met"] / agg["sla_total"] * 100, 1)
                if agg["sla_total"] else 100.0,
                "response": round(agg["resp_sum"] / agg["resp_n"])
                if agg["resp_n"] else 0,
                "velocity": round(agg["vel_sum"] / agg["vel_n"], 1)
                if agg["vel_n"] else 0,
            })
        return out

    @staticmethod
    def _team_rows(teams, team_names, team_sla) -> list[dict]:
        out = []
        for t in teams:
            s = team_sla.get(t.id, {"total": 0, "breached": 0})
            total, breached = s["total"], s["breached"]
            comp = round((total - breached) / total * 100, 1) if total else 100.0
            out.append({
                "name": t.name,
                "team": str(t.id),
                "total": total,
                "breached": breached,
                "comp": comp,
            })
        return out

    @staticmethod
    def _funnel(counts) -> list[dict]:
        rows = [
            ("Fresh Leads", StageCode.FRESH),
            ("Follow Up", StageCode.FOLLOW_UP),
            ("Not Reached", StageCode.NOT_REACHED),
            ("Meeting Scheduled", StageCode.MEETING),
            ("Interested", StageCode.INTERESTED),
        ]
        return [{"stage": label, "val": counts.get(code, 0)} for label, code in rows]
