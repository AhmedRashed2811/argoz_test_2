from django.contrib import admin

from .models import (
    DistributionCandidateSnapshot,
    DistributionRun,
    LeadRetryAttempt,
    RotationPointer,
)


@admin.register(DistributionRun)
class DistributionRunAdmin(admin.ModelAdmin):
    list_display = ("lead", "method_code", "status", "selected_salesman", "started_at")
    list_filter = ("status", "method_code")


@admin.register(DistributionCandidateSnapshot)
class DistributionCandidateSnapshotAdmin(admin.ModelAdmin):
    list_display = ("run", "candidate_type", "candidate_user", "is_eligible")
    list_filter = ("candidate_type", "is_eligible")


@admin.register(RotationPointer)
class RotationPointerAdmin(admin.ModelAdmin):
    list_display = ("company", "pointer_code", "scope", "current_index")
    list_filter = ("pointer_code",)


@admin.register(LeadRetryAttempt)
class LeadRetryAttemptAdmin(admin.ModelAdmin):
    list_display = ("lead", "team", "salesman", "attempt_number", "status")
    list_filter = ("status",)
