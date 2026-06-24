"""Accounts forms (docs §15.1: input cleaning only; cross-entity rules in
services). The user-creation wizard's role defaults live in the view/service."""
from django import forms

from apps.authorization.models import RoleGroup

from .models import User


class UserCreateForm(forms.Form):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    phone = forms.CharField(max_length=32, required=False)
    job_title = forms.CharField(max_length=120, required=False)
    default_role = forms.ModelChoiceField(
        queryset=RoleGroup.objects.none(), required=False
    )
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields["default_role"].queryset = RoleGroup.objects.filter(
                company=company, is_active=True
            )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
