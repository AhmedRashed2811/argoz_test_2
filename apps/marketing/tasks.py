"""Marketing background jobs (docs §12.1). Recalculate campaign metrics/ROI on a
schedule or after changes. Calls services only."""
from __future__ import annotations

from celery import shared_task


@shared_task
def recalculate_campaign_metrics(campaign_id: str | None = None):
    from .models import Campaign
    from .services import CampaignBudgetService

    qs = (
        Campaign.objects.filter(id=campaign_id)
        if campaign_id
        else Campaign.objects.filter(archived_at__isnull=True)
    )
    count = 0
    for campaign in qs:
        CampaignBudgetService.recalculate(campaign=campaign)
        count += 1
    return count
