"""Accounts forms (docs §15.1: input cleaning only; cross-entity rules in
services). The user-creation wizard's role defaults live in the view/service."""
from django import forms

from apps.authorization.models import RoleGroup

from .models import Team, User


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
            ).exclude(code="BROKERS")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class UserEditForm(forms.Form):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    phone = forms.CharField(max_length=32, required=False)
    job_title = forms.CharField(max_length=120, required=False)
    default_role = forms.ModelChoiceField(
        queryset=RoleGroup.objects.none(), required=False
    )
    password = forms.CharField(widget=forms.PasswordInput, required=False, help_text="Leave blank to keep current password")

    def __init__(self, *args, company=None, user_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_instance = user_instance
        if company is not None:
            self.fields["default_role"].queryset = RoleGroup.objects.filter(
                company=company, is_active=True
            ).exclude(code="BROKERS")

    def clean_email(self):
        email = self.cleaned_data["email"]
        qs = User.objects.filter(email=email)
        if self.user_instance is not None:
            qs = qs.exclude(pk=self.user_instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class TeamForm(forms.Form):
    name = forms.CharField(max_length=150)
    region = forms.CharField(max_length=120, required=False)
    order_index = forms.IntegerField(required=False, initial=0)

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean_order_index(self):
        return self.cleaned_data.get("order_index") or 0
