"""Audit engine (docs §6). Append-only AuditLog is the single trail for every
module; field diffs, exports, and job runs get focused tables."""
from django.db import models

from apps.core.constants import AuditAction
from apps.core.models import BaseModel


class AuditLog(BaseModel):
    """Immutable audit record (docs §6.2). Never updated except archival meta."""

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="audit_logs",
        null=True, blank=True,
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_actions",
    )
    action = models.CharField(max_length=40, choices=AuditAction.CHOICES)
    module = models.CharField(max_length=60, blank=True)
    entity_type = models.CharField(max_length=120)
    entity_id = models.CharField(max_length=64)
    entity_display = models.CharField(max_length=255, blank=True)
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    changed_fields = models.JSONField(null=True, blank=True)
    request_meta = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    source = models.CharField(max_length=40, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "entity_type", "entity_id"]),
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.entity_type}#{self.entity_id}"


class AuditEventField(BaseModel):
    """Normalized field diff for easier filtering (docs §6.2)."""

    audit = models.ForeignKey(
        AuditLog, on_delete=models.CASCADE, related_name="field_changes"
    )
    field_name = models.CharField(max_length=120)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    old_display = models.TextField(blank=True)
    new_display = models.TextField(blank=True)


class DataExportLog(BaseModel):
    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="export_logs"
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    report_code = models.CharField(max_length=120)
    filters = models.JSONField(null=True, blank=True)
    row_count = models.IntegerField(default=0)
    file_name = models.CharField(max_length=255, blank=True)


class JobExecutionLog(BaseModel):
    """Background job results for ops troubleshooting (docs §6.2, §12)."""

    task_name = models.CharField(max_length=150)
    task_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    processed_count = models.IntegerField(default=0)
    error = models.TextField(blank=True)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["task_name", "status"])]
