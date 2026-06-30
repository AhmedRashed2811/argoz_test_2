"""Personal notebook — private notes a user keeps for themselves (mirrors the
chat pattern, but single-owner). Fields/relations only; behaviour lives in
services.py. A Note is owned by exactly one user and never shared."""
from django.db import models

from apps.core.models import BaseModel, CompanyOwnedModel


class Note(BaseModel, CompanyOwnedModel):
    owner = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notes"
    )
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["owner", "-updated_at"])]
