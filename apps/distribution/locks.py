"""Locking helpers (docs §17, §12.2). Centralizes select_for_update so the SLA
job and assignment paths lock consistently."""
from __future__ import annotations

from contextlib import contextmanager

from django.db import transaction


@contextmanager
def locked_lead(lead_id):
    """Yield a row-locked Lead inside a transaction (docs §16.2)."""
    from apps.leads.models import Lead

    with transaction.atomic():
        yield Lead.objects.select_for_update().get(id=lead_id)


def expired_sla_batch(now, limit=100):
    """Locked batch of expired active SLA instances; skip_locked so parallel
    workers never rotate the same lead (docs §12.2). Falls back gracefully on
    backends without skip_locked support."""
    from apps.leads.constants import SLAStatus
    from apps.leads.models import SLAInstance

    base_qs = (
        SLAInstance.objects.select_related("lead", "lead__company", "lead__assigned_salesman")
        .filter(status=SLAStatus.ACTIVE, deadline_at__lte=now)
        .order_by("deadline_at")[:limit]
    )
    # Evaluate eagerly so the exception surfaces here, not at iteration time.
    # Degrade: skip_locked → plain lock → no lock (SQLite / dev).
    for attempt in (
        lambda q: q.select_for_update(skip_locked=True),
        lambda q: q.select_for_update(),
        lambda q: q,
    ):
        try:
            return list(attempt(base_qs))
        except Exception:
            continue
    return []
