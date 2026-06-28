"""Read-side shaping for lead tables and the lead timeline (docs §4, §8).

Pure presentation: turn Lead rows / related history into the JSON dicts the
front-end tables and modals expect. No DB writes, no business rules — kept out
of the API views so those stay thin."""
from __future__ import annotations

from django.utils import timezone

from ..constants import ActiveStatus, AssignmentMethod, StageCode


def _ms(dt):
    """Datetime -> epoch milliseconds (JS-friendly), or None."""
    return int(dt.timestamp() * 1000) if dt else None


def _actor_name(user):
    """Display name of the user who performed an action (not the lead owner)."""
    if user is None:
        return None
    return user.get_full_name() or user.email


class LeadSerializationService:
    """Shapes leads + their history for the JSON endpoints."""

    @staticmethod
    def campaign_child_names(leads_list):
        """Resolve campaign_child_id -> record name across marketing record tables."""
        from apps.marketing.models import (
            EventRecord, ExhibitionRecord, SocialMediaAdRecord, StreetAdRecord,
            TVAdRecord,
        )

        child_ids = [l.campaign_child_id for l in leads_list if l.campaign_child_id]
        names = {}
        if child_ids:
            for model in (EventRecord, TVAdRecord, StreetAdRecord,
                          SocialMediaAdRecord, ExhibitionRecord):
                for pk, name in model.objects.filter(
                    id__in=child_ids
                ).values_list("id", "name"):
                    names[str(pk)] = name
        return names

    @classmethod
    def rows(cls, leads_list, *, assignment=False, admin=False):
        """Shape a list of leads for a table.

        assignment → add assignedTo / assignedToId / team columns.
        admin      → also add createdBy / lifecycle columns.
        """
        names = cls.campaign_child_names(leads_list)
        out = []
        for l in leads_list:
            row = {
                "id": str(l.id),
                "name": l.name,
                "phone": l.phone,
                "source": l.source.name if l.source_id else "",
                "specificSource": names.get(str(l.campaign_child_id), "") if l.campaign_child_id else "",
                "campaign": l.campaign.name if l.campaign_id else "",
                "campaign_child_type": l.campaign_child_type,
                "broker": l.broker_owner.name if l.broker_owner_id else "",
                "stage": l.current_stage.name if l.current_stage_id else "Fresh",
                "active": l.active_status == ActiveStatus.ACTIVE,
                "createdAt": _ms(l.created_at),
                "updatedAt": _ms(l.updated_at),
                "slaDeadline": _ms(l.sla_deadline),
            }
            if assignment or admin:
                sm = l.assigned_salesman
                row["assignedTo"] = (sm.get_full_name() or sm.email) if sm else ""
                row["assignedToId"] = str(l.assigned_salesman_id) if l.assigned_salesman_id else ""
                row["team"] = l.assigned_team.name if l.assigned_team_id else ""
            if admin:
                row["createdBy"] = (l.created_by.get_full_name() or l.created_by.email) if l.created_by_id else ""
                row["lifecycle"] = (l.metadata or {}).get("lifecycle", "New")
            out.append(row)
        return out

    @staticmethod
    def history(lead):
        """Build the timeline for one lead from stage / assignment / follow-up /
        meeting / note records. Each item carries `by` = the actor."""
        items = [{
            "type": "created", "ts": _ms(lead.created_at), "label": "Lead Created",
            "feedback": "Lead added to the system.", "by": _actor_name(lead.created_by),
        }]
        for h in lead.stage_history.all():
            if h.from_stage_id == h.to_stage_id:
                continue
            # Meeting/Follow-up stage moves already surface as their own timeline
            # item (below); skip the redundant "Stage changed to …" entry.
            if h.to_stage_id and h.to_stage.code in (StageCode.MEETING, StageCode.FOLLOW_UP):
                continue
            to_name = h.to_stage.name if h.to_stage_id else ""
            clean_reason = h.reason
            if clean_reason and "By Turn index" in clean_reason:
                clean_reason = "By Turn Rotation"
            items.append({
                "type": "stage", "ts": _ms(h.changed_at),
                "label": f"Stage changed to {to_name}", "feedback": clean_reason or None,
                "by": _actor_name(h.actor),
            })
        for a in lead.assignment_history.all():
            from_name = a.from_salesman.get_full_name() or a.from_salesman.email if a.from_salesman else None
            to_name = a.to_salesman.get_full_name() or a.to_salesman.email if a.to_salesman else None

            clean_reason = a.reason
            if clean_reason and "By Turn index" in clean_reason:
                clean_reason = "By Turn Rotation"

            if from_name and from_name != to_name:
                label = f"Reassigned from {from_name} to {to_name}"
            else:
                label = f"Assigned to {to_name}"

            auto = a.assignment_method != AssignmentMethod.MANUAL
            items.append({
                "type": "assignment",
                "ts": _ms(a.assigned_at),
                "label": label,
                "feedback": clean_reason or None,
                "by": "System" if auto else _actor_name(a.actor),
            })
        for f in lead.followups.all():
            d = timezone.localtime(f.scheduled_at)
            items.append({
                "type": "followup", "ts": _ms(f.created_at),
                "label": f"Follow-up scheduled for {d.date().isoformat()}",
                "reminderDate": d.date().isoformat(), "reminderTime": d.strftime("%H:%M"),
                "feedback": f.notes or None, "by": _actor_name(f.created_by),
            })
        for m in lead.meetings.all():
            d = timezone.localtime(m.scheduled_start)
            items.append({
                "type": "meeting", "ts": _ms(m.created_at),
                "label": f"Meeting scheduled for {d.date().isoformat()}",
                "meetingDate": d.date().isoformat(), "meetingTime": d.strftime("%H:%M"),
                "meetingLocation": m.location or None, "by": _actor_name(m.created_by),
            })
        for n in lead.lead_notes.all():
            if n.is_deleted:
                continue
            items.append({"type": "note", "ts": _ms(n.created_at),
                          "label": "Note added", "feedback": n.body,
                          "by": _actor_name(n.created_by)})

        items.sort(key=lambda i: i["ts"] or 0, reverse=True)
        return items
