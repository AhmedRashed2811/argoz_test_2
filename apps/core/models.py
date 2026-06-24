"""Shared abstract base models (docs §15.1: models.py = fields/relations only).

All concrete business models compose these so UUID PKs, timestamps, company
scoping (SaaS-ready, docs §2.3) and soft-delete (docs §17) stay DRY.
"""
import uuid

from django.db import models


class UUIDModel(models.Model):
    """UUID primary key. Most catalog entities use UUIDField id (docs §11)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CompanyOwnedModel(models.Model):
    """Attaches company scope to business tables even in the one-company release
    so a future SaaS migration is not a rewrite (docs §2.3)."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def soft_delete(self):
        return self.update(is_deleted=True)


class SoftDeleteModel(models.Model):
    """Prefer archive/soft-delete for business records (docs §17)."""

    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """Convenience base: UUID id + timestamps."""

    class Meta:
        abstract = True
