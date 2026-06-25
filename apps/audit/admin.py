"""Audit is append-only (docs §6.2) — admin is strictly read-only."""
from django.contrib import admin

from .models import AuditEventField, AuditLog, DataExportLog, JobExecutionLog


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


@admin.register(AuditEventField)
class AuditEventFieldAdmin(admin.ModelAdmin):
    list_display = ("audit", "field_name", "old_value", "new_value")
    readonly_fields = [f.name for f in AuditEventField._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DataExportLog)
class DataExportLogAdmin(admin.ModelAdmin):
    list_display = ("company", "actor", "report_code", "row_count", "created_at")
    readonly_fields = [f.name for f in DataExportLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JobExecutionLog)
class JobExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("task_name", "status", "processed_count", "finished_at")
    list_filter = ("task_name", "status")
