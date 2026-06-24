"""Existing-client lead handling (leads spec §4.2h). Policy either preserves the
prior salesman relationship (if still active) or redistributes."""
from __future__ import annotations

from django.db import transaction

from apps.policies.constants import PolicyCode
from apps.policies.services import PolicyResolver

from ..constants import SourceCode
from ..models import Client
from .lead_creation_service import LeadCreationService

PRESERVE = "PRESERVE_PRIOR_RELATIONSHIP"
REDISTRIBUTE = "REDISTRIBUTE"


class ExistingClientService:
    @staticmethod
    @transaction.atomic
    def create_from_client(*, company, name, phone, actor=None, request_meta=None,
                           **extra):
        policy = PolicyResolver.option_code(
            company, PolicyCode.EXISTING_CLIENT_POLICY, default=PRESERVE
        )
        prior = (
            Client.objects.filter(company=company, phone=phone)
            .select_related("original_salesman")
            .first()
        )
        preserve_to = None
        if policy == PRESERVE and prior and prior.original_salesman:
            # Reassign to the same salesman only if still active (spec §4.2h).
            if prior.original_salesman.is_active:
                preserve_to = prior.original_salesman

        lead = LeadCreationService.create(
            company=company, source_code=SourceCode.EXISTING_CLIENT, name=name,
            phone=phone, actor=actor, request_meta=request_meta,
            assigned_salesman=preserve_to,
            auto_distribute=preserve_to is None,
            **extra,
        )
        return lead
