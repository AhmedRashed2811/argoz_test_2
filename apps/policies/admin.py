"""Backend admin for policy config (docs §7) until the UI editor is built."""
from django.contrib import admin

from .models import (
    CompanyPolicyValue,
    PolicyDefinition,
    PolicyOptionDefinition,
    PolicyParameter,
    StrategyDefinition,
)


class OptionInline(admin.TabularInline):
    model = PolicyOptionDefinition
    extra = 0


@admin.register(PolicyDefinition)
class PolicyDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "module", "value_type", "is_active")
    search_fields = ("code", "name")
    inlines = [OptionInline]


class ParameterInline(admin.TabularInline):
    model = PolicyParameter
    extra = 0


@admin.register(CompanyPolicyValue)
class CompanyPolicyValueAdmin(admin.ModelAdmin):
    list_display = ("company", "policy", "selected_option")
    list_filter = ("company",)
    inlines = [ParameterInline]


admin.site.register(StrategyDefinition)
