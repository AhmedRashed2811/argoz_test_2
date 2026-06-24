"""Policy management views (docs §7, §14): list policies and set the company's
selected option/value through PolicyManagementService."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.authorization.decorators import crm_permission_required

from .models import CompanyPolicyValue, PolicyDefinition
from .services import PolicyManagementService


class PolicyValueForm(forms.Form):
    option = forms.ChoiceField(choices=[], required=False)
    value_json = forms.CharField(widget=forms.Textarea, required=False,
                                 help_text="Raw JSON for non-option policies")

    def __init__(self, *args, policy=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["option"].choices = [("", "—")] + [
            (o.code, o.label) for o in policy.options.all()
        ]


@login_required
@crm_permission_required("policies.company.manage")
def policy_list(request):
    values = {v.policy_id: v for v in
              CompanyPolicyValue.objects.filter(company=request.company)
              .select_related("selected_option")}
    rows = []
    for policy in PolicyDefinition.objects.filter(is_active=True).order_by("module"):
        v = values.get(policy.id)
        current = ""
        if v:
            current = (v.selected_option.label if v.selected_option
                       else v.value_json)
        rows.append({"policy": policy, "current": current})
    return render(request, "policies/policy_list.html", {"rows": rows})


@login_required
@crm_permission_required("policies.company.manage")
def policy_edit(request, policy_id):
    policy = get_object_or_404(PolicyDefinition, id=policy_id)
    form = PolicyValueForm(request.POST or None, policy=policy)
    if request.method == "POST" and form.is_valid():
        import json

        option = policy.options.filter(code=form.cleaned_data["option"]).first()
        raw = form.cleaned_data["value_json"].strip()
        value_json = json.loads(raw) if raw else None
        PolicyManagementService.set_value(
            company=request.company, code=policy.code, option=option,
            value_json=value_json, updated_by=request.user,
        )
        messages.success(request, "Policy updated.")
        return redirect("policies:list")
    return render(request, "form.html", {"title": f"Policy: {policy.name}", "form": form})
