"""Manual distribution board scope + access (leads spec §8.1).

Two scopes, enforced server-side on every endpoint:
  leads.distribution.manual_all  → any salesman / sales head, all company leads
  leads.distribution.team_manual → a sales head: only their own team members
                                   (or self), only their team's leads
"""
from __future__ import annotations

from apps.accounts.models import Team
from apps.authorization.services import EffectivePermissionResolver

from ..constants import ActiveStatus
from ..models import Lead

_MANUAL_PERMS = ("leads.distribution.manual_all", "leads.distribution.team_manual")


class ManualDistributionService:
    @staticmethod
    def can_access(user) -> bool:
        return any(EffectivePermissionResolver.has(user, c) for c in _MANUAL_PERMS)

    @staticmethod
    def scope(user, company):
        """('all', None) | ('team', [team_ids]) | (None, None). manual_all wins."""
        if EffectivePermissionResolver.has(user, "leads.distribution.manual_all"):
            return "all", None
        if EffectivePermissionResolver.has(user, "leads.distribution.team_manual"):
            team_ids = list(Team.objects.filter(
                company=company, sales_head=user, is_active=True
            ).values_list("id", flat=True))
            return "team", team_ids
        return None, None

    @classmethod
    def leads(cls, user, company):
        """Leads awaiting manual distribution that the user may handle (docs §8.1).

        A lead needs manual distribution exactly when it is active but has no
        salesman — the state every escalation path leaves it in. Scope:
          manual_all  → all such leads company-wide;
          team_manual → those already routed to a team this user heads.
        """
        scope, team_ids = cls.scope(user, company)
        base = Lead.objects.filter(
            company=company,
            active_status=ActiveStatus.ACTIVE,
            assigned_salesman__isnull=True,
        ).select_related(
            "source", "current_stage", "assigned_salesman", "assigned_team",
            "campaign", "broker_owner",
        )
        if scope == "all":
            return base
        if scope == "team":
            return base.filter(assigned_team_id__in=team_ids)
        return base.none()

    @classmethod
    def assignable_people(cls, user, company):
        """[(user, team)] the user may assign to, de-duplicated. manual_all → every
        active salesman + sales head; team_manual → the head's own members + self."""
        scope, team_ids = cls.scope(user, company)
        if scope == "all":
            teams = Team.objects.filter(company=company, is_active=True)
        elif scope == "team":
            teams = Team.objects.filter(id__in=team_ids)
        else:
            return []
        teams = teams.select_related("sales_head").prefetch_related(
            "members__user", "members__team")
        seen, out = set(), []
        for t in teams:
            for m in t.members.all():
                if m.user.is_active and m.user_id not in seen:
                    seen.add(m.user_id)
                    out.append((m.user, t))
            head = t.sales_head
            if head and head.is_active and head.id not in seen:
                seen.add(head.id)
                out.append((head, t))
        return out

    @classmethod
    def salesmen_with_loads(cls, user, company):
        """Assignable salesmen + their active lead count, shaped for the table."""
        from apps.distribution.selectors import batch_candidate_loads

        people = cls.assignable_people(user, company)
        loads = batch_candidate_loads([u for u, _ in people], company)
        out = []
        for u, team in people:
            active, _last = loads.get(u.id, (0, None))
            out.append({
                "id": str(u.id), "name": u.get_full_name() or u.email,
                "team": team.name, "team_id": str(team.id), "count": active,
            })
        return out

    @classmethod
    def resolve_assignee(cls, user, company, salesman_id):
        """(salesman, team) the user may assign to, or None if out of scope."""
        allowed = {
            str(u.id): (u, team)
            for u, team in cls.assignable_people(user, company)
        }
        return allowed.get(salesman_id or "")
