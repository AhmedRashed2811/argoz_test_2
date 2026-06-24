"""Audit is append-only (docs §6.2) — admin is strictly read-only."""
from django.contrib import admin

from .models import AuditLog, JobExecutionLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "entity_type", "entity_id", "actor", "company",
                    "created_at")
    list_filter = ("action", "module")
    search_fields = ("entity_type", "entity_id")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JobExecutionLog)
class JobExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("task_name", "status", "processed_count", "finished_at")
    list_filter = ("task_name", "status")
