"""Lead forms (docs §15.1). Field cleaning only; distribution/stage/SLA rules
stay in services. Phone is revalidated backend-side per leads spec §4.1."""
from django import forms

from apps.accounts.models import Language, Team, User
from apps.accounts.models import Broker

from .constants import Origin
from .models import LeadSourceDefinition


class LeadCreateForm(forms.Form):
    source_code = forms.ChoiceField(choices=[])
    name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=32)
    email = forms.EmailField(required=False)
    country_code = forms.CharField(max_length=8, required=False)
    origin = forms.ChoiceField(choices=Origin.CHOICES, initial=Origin.DIRECT)
    language = forms.ModelChoiceField(queryset=Language.objects.none(), required=False)
    broker_owner = forms.ModelChoiceField(queryset=Broker.objects.none(), required=False)
    referrer_name = forms.CharField(max_length=150, required=False)

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_code"].choices = [
            (s.code, s.name)
            for s in LeadSourceDefinition.objects.filter(is_active=True)
        ]
        self.fields["language"].queryset = Language.objects.filter(is_active=True)
        if company is not None:
            self.fields["broker_owner"].queryset = Broker.objects.filter(company=company)

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if len(phone) < 6:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone


class ManualAssignmentForm(forms.Form):
    """Assign to a team (head decides) or directly to a salesman (docs §8.3)."""

    team = forms.ModelChoiceField(queryset=Team.objects.none(), required=False)
    salesman = forms.ModelChoiceField(queryset=User.objects.none(), required=False)
    reason = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields["team"].queryset = Team.objects.filter(
                company=company, is_active=True
            )
            self.fields["salesman"].queryset = User.objects.filter(
                profile__company=company, is_active=True
            )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("team") and not cleaned.get("salesman"):
            raise forms.ValidationError("Choose a team or a salesman.")
        return cleaned


class FollowUpForm(forms.Form):
    scheduled_at = forms.DateTimeField()
    notes = forms.CharField(widget=forms.Textarea, required=False)


class MeetingForm(forms.Form):
    scheduled_start = forms.DateTimeField()
    scheduled_end = forms.DateTimeField(required=False)
    location = forms.CharField(max_length=255, required=False)


class StageChangeForm(forms.Form):
    to_stage_code = forms.ChoiceField(choices=[])
    reason = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import LeadStageDefinition

        self.fields["to_stage_code"].choices = [
            (s.code, s.name) for s in LeadStageDefinition.objects.all()
        ]


class WalkInForm(forms.Form):
    """Walk-in intake form (leads spec §4.2d). Website must be an option in
    how_did_you_know — enforced by the seed command."""

    name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=32)
    how_did_you_know = forms.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import HowDidYouKnowOption

        self.fields["how_did_you_know"].choices = [
            (o.code, o.name)
            for o in HowDidYouKnowOption.objects.filter(is_active=True)
        ]
