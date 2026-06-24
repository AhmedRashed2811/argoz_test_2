"""Finance read queries (docs §15.1)."""
from apps.marketing.constants import ApprovalStatus
from apps.marketing.models import Campaign


def pending_review(company):
    return Campaign.objects.filter(
        company=company, approval_status=ApprovalStatus.PENDING, archived_at__isnull=True
    ).select_related("company", "created_by").order_by("-created_at")
