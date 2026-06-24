"""Authorization forms (docs §4.4). Friendly names first, codes secondary."""
from django import forms

from .models import Effect, PermissionDefinition, RoleGroup


class RoleForm(forms.ModelForm):
    class Meta:
        model = RoleGroup
        fields = ["code", "name", "description", "is_active"]


class UserOverrideForm(forms.Form):
    permission = forms.ModelChoiceField(
        queryset=PermissionDefinition.objects.filter(is_active=True)
    )
    effect = forms.ChoiceField(choices=Effect.CHOICES)
    reason = forms.CharField(widget=forms.Textarea, required=False)
