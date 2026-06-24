"""Marketing forms (docs §10, §14). Dynamic type selection drives which child
formsets appear in the UI; heavy child creation stays in CampaignCreationService."""
from django import forms

from .constants import CampaignType


class CampaignForm(forms.Form):
    name = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea, required=False)
    start_date = forms.DateField()
    end_date = forms.DateField()
    target_type = forms.CharField(max_length=30, required=False)
    selected_types = forms.MultipleChoiceField(
        choices=[(c, c.replace("_", " ").title()) for c in CampaignType.ALL],
        widget=forms.CheckboxSelectMultiple, required=False,
    )

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("End date cannot be before start date.")
        return cleaned


class OtherCostForm(forms.Form):
    value = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    reason = forms.CharField(widget=forms.Textarea)
