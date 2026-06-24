"""Distribution mechanics (docs §11, §16). Records each engine run and the
candidate evaluation so a selection is fully explainable and auditable."""
from django.db import models

from apps.core.models import BaseModel, CompanyOwnedModel


class DistributionRun(BaseModel, CompanyOwnedModel):
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.CASCADE, related_name="distribution_runs"
    )
    method_code = models.CharField(max_length=40)
    scope_mode = models.CharField(max_length=40, blank=True)
    language = models.ForeignKey(
        "accounts.Language", on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=20, default="PENDING")
    selected_team = models.ForeignKey(
        "accounts.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    selected_salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)


class DistributionCandidateSnapshot(BaseModel):
    """Explains why a candidate was selected/skipped (docs §11)."""

    run = models.ForeignKey(
        DistributionRun, on_delete=models.CASCADE, related_name="candidates"
    )
    candidate_type = models.CharField(max_length=20)  # TEAM / SALESMAN
    candidate_id = models.UUIDField(null=True, blank=True)
    candidate_user = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    active_lead_count = models.IntegerField(default=0)
    last_received_at = models.DateTimeField(null=True, blank=True)
    is_eligible = models.BooleanField(default=True)
    rejection_reason = models.TextField(blank=True)


class RotationPointer(BaseModel, CompanyOwnedModel):
    """By Turn / walk-in rotation cursor. Locked before read/update (docs §17)."""

    pointer_code = models.CharField(max_length=80)
    scope = models.CharField(max_length=80, blank=True)
    current_index = models.IntegerField(default=0)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "pointer_code", "scope"],
                name="uniq_rotation_pointer",
            )
        ]


class LeadRetryAttempt(BaseModel):
    """Retry attempts inside a team before escalation (docs §8.3)."""

    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.CASCADE, related_name="retry_attempts"
    )
    team = models.ForeignKey(
        "accounts.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    salesman = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    attempt_number = models.IntegerField(default=1)
    started_at = models.DateTimeField(auto_now_add=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="ACTIVE")
    result = models.CharField(max_length=20, blank=True)
    policy_snapshot = models.JSONField(null=True, blank=True)
