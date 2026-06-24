"""Accounts read queries (docs §15.1)."""
from .models import User


def users_for_company(company):
    return (
        User.objects.filter(profile__company=company)
        .select_related("profile", "profile__default_role")
        .order_by("email")
    )
