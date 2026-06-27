"""Accounts services (docs §15.1: workflows live here, not views). User-creation
wizard with role defaults is owned by the authorization app (§4.4)."""
from __future__ import annotations

from django.db import transaction

from .models import Language, Team, TeamMember, User, UserLanguage, UserProfile, Broker


class UserService:
    @staticmethod
    @transaction.atomic
    def create_user(*, company, email, password=None, default_role=None,
                    first_name="", last_name="", phone="", permission_codes=None,
                    language_codes=None, created_by=None, request_meta=None, **profile):
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

            PermissionManagementService.assign_role(user=user, role=default_role, assigned_by=created_by, request_meta=request_meta, audit=False)

        # Determine and create overrides if custom permission_codes are provided
        if permission_codes is not None:
            from apps.authorization.services import PermissionManagementService
            PermissionManagementService.update_user_overrides(
                user=user,
                permission_codes=permission_codes,
                created_by=created_by,
                request_meta=request_meta,
                audit=False,
            )

        if default_role and default_role.code == "SALES" and language_codes:
            langs = [Language.objects.get_or_create(code=c, defaults={"name": c})[0] for c in language_codes]
            UserLanguage.objects.bulk_create([
                UserLanguage(user=user, language=lang)
                for lang in langs
            ], ignore_conflicts=True)

        # Audit creation
        from apps.audit.services import AuditService, DiffService
        from apps.core.constants import AuditAction

        after_data = DiffService.snapshot(user, fields=["email", "first_name", "last_name", "phone", "is_active"])
        after_data.update(DiffService.snapshot(user.profile, fields=["job_title", "department", "availability_status"]))
        if default_role:
            after_data["default_role"] = default_role.name

        AuditService.log(
            action=AuditAction.CREATE, instance=user, actor=created_by, company=company,
            module="accounts", request_meta=request_meta,
            after=after_data, entity_display=user.email,
        )

        return user

    @staticmethod
    @transaction.atomic
    def update_user(*, user, email, password=None, default_role=None,
                    first_name="", last_name="", phone="", permission_codes=None,
                    language_codes=None, created_by=None, request_meta=None, **profile_data):
        from apps.audit.services import AuditService, DiffService
        from apps.core.constants import AuditAction

        # Capture state before update
        before_data = DiffService.snapshot(user, fields=["email", "first_name", "last_name", "phone", "is_active"])
        before_data.update(DiffService.snapshot(user.profile, fields=["job_title", "department", "availability_status"]))
        if user.profile.default_role:
            before_data["default_role"] = user.profile.default_role.name

        user.email = email
        if password:
            user.set_password(password)
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.save()

        profile = user.profile
        profile.default_role = default_role
        for key, value in profile_data.items():
            setattr(profile, key, value)
        profile.save()

        from apps.authorization.models import UserRole
        if default_role is not None:
            from apps.authorization.services import PermissionManagementService
            PermissionManagementService.assign_role(user=user, role=default_role, assigned_by=created_by, request_meta=request_meta, audit=False)
        else:
            UserRole.objects.filter(user=user).update(is_active=False)

        if permission_codes is not None:
            from apps.authorization.services import PermissionManagementService
            PermissionManagementService.update_user_overrides(
                user=user,
                permission_codes=permission_codes,
                created_by=created_by,
                request_meta=request_meta,
                audit=True,
            )

        if language_codes is not None:
            UserLanguage.objects.filter(user=user).delete()
            role = default_role or (user.profile.default_role if hasattr(user, "profile") else None)
            if role and role.code == "SALES" and language_codes:
                langs = [Language.objects.get_or_create(code=c, defaults={"name": c})[0] for c in language_codes]
                UserLanguage.objects.bulk_create([UserLanguage(user=user, language=lang) for lang in langs])

        # Capture state after update
        after_data = DiffService.snapshot(user, fields=["email", "first_name", "last_name", "phone", "is_active"])
        after_data.update(DiffService.snapshot(user.profile, fields=["job_title", "department", "availability_status"]))
        if default_role:
            after_data["default_role"] = default_role.name

        AuditService.log(
            action=AuditAction.UPDATE, instance=user, actor=created_by, company=user.profile.company,
            module="accounts", request_meta=request_meta,
            before=before_data, after=after_data,
            entity_display=user.email,
        )
        return user

    @staticmethod
    @transaction.atomic
    def delete_user(*, user, actor=None, request_meta=None):
        user.is_active = False
        user.save()
        profile = user.profile
        profile.availability_status = "OFFLINE"
        profile.save()

        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        AuditService.log(
            action=AuditAction.DELETE, instance=user, actor=actor, company=profile.company,
            module="accounts", request_meta=request_meta,
            reason="Deactivated user profile",
            entity_display=user.email,
        )

    @staticmethod
    @transaction.atomic
    def destroy_user(*, user, actor=None, request_meta=None) -> None:
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        email = user.email
        company = user.profile.company

        AuditService.log(
            action=AuditAction.DELETE, instance=user, actor=actor, company=company,
            module="accounts", request_meta=request_meta,
            reason="Permanently deleted user account",
            entity_display=email,
        )

        user.delete()

    @staticmethod
    @transaction.atomic
    def activate_user(*, user, actor=None, request_meta=None):
        user.is_active = True
        user.save()
        profile = user.profile
        profile.availability_status = "AVAILABLE"
        profile.save()

        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        AuditService.log(
            action=AuditAction.UPDATE, instance=user, actor=actor, company=profile.company,
            module="accounts", request_meta=request_meta,
            reason="Activated user profile",
            after={"is_active": True, "availability_status": "AVAILABLE"},
            entity_display=user.email,
        )

    @staticmethod
    def directory_payload(*, company):
        """Serialize the user directory for the AJAX users page (read-only).
        Heavy query/annotation lives in the selector; this only shapes JSON."""
        from apps.authorization.models import RoleGroup

        from .selectors import user_directory

        users = []
        for u in user_directory(company):
            profile = getattr(u, "profile", None)
            role = profile.default_role if profile else None
            users.append({
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phone": u.phone or None,
                "is_active": u.is_active,
                "profile": {
                    "job_title": profile.job_title if profile else "",
                    "department": profile.department if profile else "",
                    "availability_status": profile.availability_status if profile else "",
                    "availability_status_display": (
                        profile.get_availability_status_display() if profile else ""
                    ),
                    "default_role": (
                        {"id": role.id, "name": role.name, "code": role.code}
                        if role else None
                    ),
                },
                "team_memberships": [
                    {"team": {"name": m.team.name}} for m in u.team_memberships.all()
                ],
                "permission_overrides_count": getattr(u, "overrides_count", 0),
                "language_codes": [ul.language.code for ul in u.languages.select_related("language").all()],
            })
        roles = [
            {"id": r.id, "name": r.name, "code": r.code}
            for r in RoleGroup.objects.filter(company=company, is_active=True).order_by("name")
        ]
        return {"users": users, "roles": roles}

    @staticmethod
    def get_user_creation_context(*, company):
        import json
        from apps.authorization.models import RoleGroup, PermissionDefinition, RolePermission

        roles = RoleGroup.objects.filter(company=company, is_active=True)
        permissions = PermissionDefinition.objects.filter(is_active=True).order_by("module", "code")
        
        role_permissions_map = {}
        for role in roles:
            allowed_codes = list(
                RolePermission.objects.filter(
                    role=role, allow=True, permission__is_active=True
                ).values_list("permission__code", flat=True)
            )
            role_permissions_map[str(role.id)] = allowed_codes
        role_permissions_json = json.dumps(role_permissions_map)
        
        return {
            "roles": roles,
            "permissions": permissions,
            "role_permissions_json": role_permissions_json,
        }

    @staticmethod
    def login_user(*, request, email, password, remember=False):
        from django.contrib.auth import authenticate, login as auth_login
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            if user.is_active:
                auth_login(request, user)
                if remember:
                    request.session.set_expiry(2592000)  # 30 days
                else:
                    request.session.set_expiry(0)  # Expires when browser closes
                profile = getattr(user, "profile", None)
                company = profile.company if profile else None
                AuditService.log(
                    action=AuditAction.LOGIN,
                    instance=user,
                    actor=user,
                    company=company,
                    module="accounts",
                    request_meta=getattr(request, "request_meta", None),
                    entity_display=user.email,
                    reason="User logged in successfully via web interface",
                )
                return user, None
            else:
                return None, "This account is deactivated."
        else:
            # Audit failed attempt if a user with this email exists
            target_user = User.objects.filter(email=email).first()
            profile = getattr(target_user, "profile", None) if target_user else None
            company = profile.company if profile else None
            AuditService.log(
                action=AuditAction.LOGIN,
                actor=target_user,
                company=company,
                module="accounts",
                request_meta=getattr(request, "request_meta", None),
                entity_display=email,
                reason=f"Failed login attempt for email: {email}",
            )
            return None, "Incorrect email or password."

    @staticmethod
    @transaction.atomic
    def change_password(*, user, current_password, new_password, request_meta=None) -> tuple[bool, str | None]:
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        if not user.check_password(current_password):
            return False, "Incorrect current password."

        user.set_password(new_password)
        user.save()

        # Log password change audit entry
        profile = getattr(user, "profile", None)
        company = profile.company if profile else None
        AuditService.log(
            action=AuditAction.UPDATE,
            instance=user,
            actor=user,
            company=company,
            module="accounts",
            request_meta=request_meta,
            reason="User updated their own password via change password screen",
            entity_display=user.email,
        )
        return True, None


class TeamService:
    @staticmethod
    def list_payload(*, company):
        from .selectors import teams_for_company
        teams = []
        for team in teams_for_company(company):
            heads = []
            members = []
            for m in team.members.all():
                user_data = {
                    "id": m.user.id,
                    "email": m.user.email,
                    "full_name": m.user.get_full_name(),
                }
                if m.position == "HEAD":
                    heads.append(user_data)
                else:
                    members.append(user_data)
            
            teams.append({
                "id": str(team.id),
                "name": team.name,
                "region": team.region,
                "order_index": team.order_index,
                "is_active": team.is_active,
                "heads": heads,
                "members": members,
            })
        return {"teams": teams}

    @staticmethod
    @transaction.atomic
    def add_member(*, team: Team, user: User, **kwargs) -> TeamMember:
        member, _ = TeamMember.objects.update_or_create(
            team=team, user=user, defaults=kwargs
        )
        return member

    @staticmethod
    @transaction.atomic
    def create_team(*, company, name, region="", order_index=0,
                    head_ids=None, member_ids=None, actor=None, request_meta=None) -> Team:
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        first_head = User.objects.filter(id__in=(head_ids or [])).first()
        team = Team.objects.create(
            company=company, name=name, region=region,
            order_index=order_index, sales_head=first_head, is_active=True,
        )
        for uid in (head_ids or []):
            TeamMember.objects.get_or_create(team=team, user_id=uid, defaults={"position": "HEAD"})
        for uid in (member_ids or []):
            TeamMember.objects.get_or_create(team=team, user_id=uid)

        AuditService.log(
            action=AuditAction.CREATE, instance=team, actor=actor, company=company,
            module="accounts", request_meta=request_meta,
            after={"name": name, "region": region, "order_index": order_index,
                   "heads": list(head_ids or []), "members": list(member_ids or [])},
            entity_display=name,
        )
        return team

    @staticmethod
    @transaction.atomic
    def update_team(*, team: Team, name, region="", order_index=0,
                    head_ids=None, member_ids=None, actor=None, request_meta=None) -> Team:
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        before = {
            "name": team.name, "region": team.region, "order_index": team.order_index,
            "heads": list(team.members.filter(position="HEAD").values_list("user_id", flat=True)),
            "members": list(team.members.exclude(position="HEAD").values_list("user_id", flat=True)),
        }

        first_head = User.objects.filter(id__in=(head_ids or [])).first()
        team.name = name
        team.region = region
        team.order_index = order_index
        team.sales_head = first_head
        team.save()

        # Sync heads
        wanted_heads = set(str(uid) for uid in (head_ids or []))
        existing_heads = {str(m.user_id): m for m in team.members.filter(position="HEAD")}
        for uid in wanted_heads - existing_heads.keys():
            TeamMember.objects.get_or_create(team=team, user_id=uid, defaults={"position": "HEAD"})
        for uid, m in existing_heads.items():
            if uid not in wanted_heads:
                m.delete()

        # Sync members
        wanted_members = set(str(uid) for uid in (member_ids or []))
        existing_members = {str(m.user_id): m for m in team.members.exclude(position="HEAD")}
        for uid in wanted_members - existing_members.keys():
            TeamMember.objects.get_or_create(team=team, user_id=uid)
        for uid, m in existing_members.items():
            if uid not in wanted_members:
                m.delete()

        AuditService.log(
            action=AuditAction.UPDATE, instance=team, actor=actor, company=team.company,
            module="accounts", request_meta=request_meta,
            before=before,
            after={"name": name, "region": region, "order_index": order_index,
                   "heads": list(head_ids or []), "members": list(member_ids or [])},
            entity_display=name,
        )
        return team

    @staticmethod
    @transaction.atomic
    def delete_team(*, team: Team, actor=None, request_meta=None) -> None:
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        AuditService.log(
            action=AuditAction.DELETE, instance=team, actor=actor, company=team.company,
            module="accounts", request_meta=request_meta,
            reason="Deleted sales team", entity_display=team.name,
        )

        team.delete()

    @staticmethod
    @transaction.atomic
    def activate_team(*, team: Team, actor=None, request_meta=None) -> None:
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        team.is_active = True
        team.save()

        AuditService.log(
            action=AuditAction.UPDATE, instance=team, actor=actor, company=team.company,
            module="accounts", request_meta=request_meta,
            after={"is_active": True}, entity_display=team.name,
        )

    @staticmethod
    def get_team_context(*, company, team=None):
        from .selectors import available_heads, available_members
        current_head_ids, current_member_ids = set(), set()
        if team is not None:
            current_head_ids = set(
                str(uid) for uid in team.members.filter(position="HEAD").values_list("user_id", flat=True)
            )
            current_member_ids = set(
                str(uid) for uid in team.members.exclude(position="HEAD").values_list("user_id", flat=True)
            )
        return {
            "available_heads": available_heads(company, team),
            "available_members": available_members(company, team),
            "current_head_ids": current_head_ids,
            "current_member_ids": current_member_ids,
        }


class AvailabilityService:
    @staticmethod
    def set_status(*, user: User, status: str) -> None:
        UserProfile.objects.filter(user=user).update(availability_status=status)


class BrokerService:
    @staticmethod
    def _brokers_role(company):
        """The BROKERS role for this company — assigning it seeds the broker's
        permission baseline (docs §4.3)."""
        from apps.authorization.models import RoleGroup
        return RoleGroup.objects.filter(company=company, code="BROKERS").first()

    @staticmethod
    @transaction.atomic
    def create_broker(
        *,
        company,
        name,
        email="",
        password=None,
        company_name="",
        phone="",
        location="",
        commission_rate=None,
        contract_start_date=None,
        contract_end_date=None,
        notes="",
        actor=None,
        request_meta=None
    ) -> Broker:
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction

        # A broker logs in as a regular user: create the account here (with the
        # BROKERS role so it inherits all broker permissions) instead of from the
        # user-creation page, and link it to the broker record.
        linked_user = None
        if email:
            if User.objects.filter(email=email).exists():
                raise ValueError("A user with this email already exists.")
            linked_user = UserService.create_user(
                company=company, email=email, password=password,
                default_role=BrokerService._brokers_role(company),
                first_name=name, phone=phone,
                created_by=actor, request_meta=request_meta,
            )

        broker = Broker.objects.create(
            company=company,
            name=name,
            email=email,
            linked_user=linked_user,
            company_name=company_name,
            phone=phone,
            location=location,
            commission_rate=commission_rate,
            contract_start_date=contract_start_date,
            contract_end_date=contract_end_date,
            notes=notes,
        )

        from apps.audit.services import DiffService
        after_data = DiffService.snapshot(broker, fields=["name", "company_name", "phone", "location", "commission_rate", "contract_start_date", "contract_end_date", "status", "notes"])

        AuditService.log(
            action=AuditAction.CREATE,
            instance=broker,
            actor=actor,
            company=company,
            module="accounts",
            request_meta=request_meta,
            after=after_data,
            entity_display=broker.name,
        )
        return broker

    @staticmethod
    @transaction.atomic
    def update_broker(
        *,
        broker_id,
        name,
        email="",
        password=None,
        company_name="",
        phone="",
        location="",
        commission_rate=None,
        contract_start_date=None,
        contract_end_date=None,
        leads_count=0,
        notes="",
        actor=None,
        request_meta=None
    ) -> Broker:
        from apps.audit.services import AuditService, DiffService
        from apps.core.constants import AuditAction

        broker = Broker.objects.select_for_update().get(id=broker_id)
        before_data = DiffService.snapshot(broker, fields=["name", "company_name", "phone", "location", "commission_rate", "contract_start_date", "contract_end_date", "leads_count", "notes"])

        # Keep the linked login account in sync (or create one if missing).
        if email or password:
            user = broker.linked_user
            if user is None and email:
                if User.objects.filter(email=email).exists():
                    raise ValueError("A user with this email already exists.")
                broker.linked_user = UserService.create_user(
                    company=broker.company, email=email, password=password,
                    default_role=BrokerService._brokers_role(broker.company),
                    first_name=name, phone=phone,
                    created_by=actor, request_meta=request_meta,
                )
            elif user is not None:
                if email and email != user.email:
                    if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                        raise ValueError("A user with this email already exists.")
                    user.email = email
                if password:
                    user.set_password(password)
                user.save()

        broker.name = name
        broker.email = email or broker.email
        broker.company_name = company_name
        broker.phone = phone
        broker.location = location
        broker.commission_rate = commission_rate
        broker.contract_start_date = contract_start_date
        broker.contract_end_date = contract_end_date
        broker.leads_count = leads_count
        broker.notes = notes
        broker.save()

        after_data = DiffService.snapshot(broker, fields=["name", "company_name", "phone", "location", "commission_rate", "contract_start_date", "contract_end_date", "leads_count", "notes"])

        AuditService.log(
            action=AuditAction.UPDATE,
            instance=broker,
            actor=actor,
            company=broker.company,
            module="accounts",
            request_meta=request_meta,
            before=before_data,
            after=after_data,
            entity_display=broker.name,
        )
        return broker

    @staticmethod
    @transaction.atomic
    def delete_broker(*, broker_id, actor=None, request_meta=None) -> None:
        from apps.audit.services import AuditService
        from apps.core.constants import AuditAction
        from apps.leads.models import Lead, BrokerLeadOwnershipHistory

        broker = Broker.objects.select_for_update().get(id=broker_id)
        company = broker.company

        # Lead history updates for leads assigned to this broker
        leads = Lead.objects.filter(broker_owner=broker)
        for lead in leads:
            BrokerLeadOwnershipHistory.objects.create(
                lead=lead,
                broker=None,
                action="BROKER_DELETED",
                old_broker=broker,
                new_broker=None,
                actor=actor,
                reason=f"Broker {broker.name} was deleted.",
            )

        AuditService.log(
            action=AuditAction.DELETE,
            instance=broker,
            actor=actor,
            company=company,
            module="accounts",
            request_meta=request_meta,
            reason="Deleted broker and unassigned its leads",
            entity_display=broker.name,
        )

        # Disable the broker's login account so it can no longer sign in.
        if broker.linked_user is not None:
            broker.linked_user.is_active = False
            broker.linked_user.save(update_fields=["is_active"])

        broker.delete()
