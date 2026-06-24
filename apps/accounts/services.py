"""Accounts services (docs §15.1: workflows live here, not views). User-creation
wizard with role defaults is owned by the authorization app (§4.4)."""
from __future__ import annotations

from django.db import transaction

from .models import Team, TeamMember, User, UserProfile


class UserService:
    @staticmethod
    @transaction.atomic
    def create_user(*, company, email, password=None, default_role=None,
                    first_name="", last_name="", phone="", **profile):
        user = User.objects.create_user(
            email=email, password=password, first_name=first_name,
            last_name=last_name, phone=phone,
        )
        UserProfile.objects.create(
            user=user, company=company, default_role=default_role, **profile
        )
        # Assigning the default role seeds the user's permission baseline (§4.3).
        if default_role is not None:
            from apps.authorization.services import PermissionManagementService

            PermissionManagementService.assign_role(user=user, role=default_role)
        return user


class TeamService:
    @staticmethod
    @transaction.atomic
    def add_member(*, team: Team, user: User, **kwargs) -> TeamMember:
        member, _ = TeamMember.objects.update_or_create(
            team=team, user=user, defaults=kwargs
        )
        return member


class AvailabilityService:
    @staticmethod
    def set_status(*, user: User, status: str) -> None:
        UserProfile.objects.filter(user=user).update(availability_status=status)
