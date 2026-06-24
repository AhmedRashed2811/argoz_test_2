"""Finance forms (docs §10.4). Reason becomes required for Semi/Not Approved —
also enforced in CampaignApprovalService."""
from django import forms

from apps.marketing.constants import ApprovalStatus


class ApprovalForm(forms.Form):
    status = forms.ChoiceField(choices=ApprovalStatus.CHOICES)
    reason = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") in ApprovalStatus.REASON_REQUIRED \
                and not (cleaned.get("reason") or "").strip():
            raise forms.ValidationError("Reason is required for this decision.")
        return cleaned
