"""External read-only leads API (Bearer / x-api-key auth).

Keeps the view thin: authenticates the request against the current company's
api_key, then returns a page of that salesman's leads already shaped for JSON.
No presentation/DB logic in the view."""
from __future__ import annotations

import hmac

from django.core.paginator import Paginator
from django.utils import timezone

from apps.core.exceptions import PermissionDenied

from ..models import Lead

PAGE_SIZE = 50


def _extract_token(request) -> str:
    """Pull the token from `Authorization: Bearer <t>` or `x-api-key: <t>`."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    return request.headers.get("x-api-key", "").strip()


class LeadApiService:
    @staticmethod
    def authenticate(request, company) -> None:
        """Constant-time compare the header token against the company api_key.
        Raises PermissionDenied on missing company or bad/empty token."""
        token = _extract_token(request)
        expected = getattr(company, "api_key", "") or ""
        if not token or not expected or not hmac.compare_digest(token, expected):
            raise PermissionDenied("Invalid or missing API credentials.")

    @staticmethod
    def leads_for_salesman(company, email: str, page_number):
        """Page of leads assigned to the salesman with `email`, newest first.
        Returns (rows, paginator_page)."""
        qs = (
            Lead.objects.filter(
                company=company, assigned_salesman__email__iexact=(email or "").strip()
            )
            .select_related("source", "current_stage")
            .order_by("-created_at")
        )
        page = Paginator(qs, PAGE_SIZE).get_page(page_number)
        rows = [LeadApiService._shape(lead) for lead in page.object_list]
        return rows, page

    @staticmethod
    def _shape(lead) -> dict:
        created = lead.created_at
        return {
            "lead_id": str(lead.id),
            "full_name": lead.name,
            "phone": f"{lead.country_code}{lead.phone}" if lead.country_code else lead.phone,
            "email": lead.email,
            "lead_source": lead.source.name if lead.source_id else None,
            "lead_status": lead.current_stage.name if lead.current_stage_id else None,
            "created_at": timezone.localtime(created).isoformat() if created else None,
        }
