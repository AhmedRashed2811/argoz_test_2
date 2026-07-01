"""Tenant lifecycle (docs §15.1: business logic lives in services, not views).

Provisioning a tenant = create its MariaDB database, build the full schema in
it, then seed the first admin + the in-tenant Company row. Activation just flips
the control-plane gate read by TenantRoutingMiddleware.
"""
from __future__ import annotations

import re

from decouple import config
from django.core.management import call_command
from django.db import transaction

from .db import ensure_connection
from .models import Tenant

_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


class TenantError(Exception):
    """Provisioning/validation failure surfaced to the panel."""


class TenantProvisioningService:
    @staticmethod
    def _validate_slug(slug: str) -> str:
        slug = (slug or "").strip().lower()
        if not _SLUG_RE.match(slug):
            raise TenantError(
                "Slug must be lowercase letters, digits and hyphens (e.g. 'acme')."
            )
        if Tenant.objects.filter(slug=slug).exists():
            raise TenantError(f"A tenant with slug '{slug}' already exists.")
        return slug

    @staticmethod
    def _create_database(cfg: dict) -> None:
        """CREATE the empty MariaDB database (bootstrap connection, no schema)."""
        import pymysql

        conn = pymysql.connect(
            host=cfg["HOST"], port=int(cfg["PORT"]),
            user=cfg["USER"], password=cfg["PASSWORD"],
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{cfg['NAME']}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def provision(*, name: str, slug: str, admin_email: str,
                  admin_password: str, paid_until=None, notes: str = "") -> Tenant:
        """Full create: validate -> build row -> create DB -> migrate -> seed.

        Synchronous (runs migrations in-request). ponytail: move to a Celery
        task if provisioning latency becomes a problem.
        """
        slug = TenantProvisioningService._validate_slug(slug)
        name = (name or "").strip() or slug
        admin_email = (admin_email or "").strip().lower()
        if not admin_email or not admin_password:
            raise TenantError("Admin email and password are required.")

        tenant = Tenant(
            name=name, slug=slug,
            db_name=f"argoz_{slug.replace('-', '_')}",
            db_host=config("MYSQL_HOST", default="127.0.0.1"),
            db_port=config("MYSQL_PORT", default="3306"),
            db_user=config("MYSQL_USER", default="root"),
            db_password=config("MYSQL_PASSWORD", default=""),
            paid_until=paid_until, notes=notes or "",
        )
        cfg = tenant.connection_config()

        TenantProvisioningService._create_database(cfg)
        alias = ensure_connection(tenant)
        call_command("migrate", database=alias, interactive=False, verbosity=0)
        TenantProvisioningService._seed(alias, name, slug, admin_email, admin_password)

        tenant.save(using="default")
        return tenant

    @staticmethod
    def _seed(alias: str, name: str, slug: str, email: str, password: str) -> None:
        """Populate the new tenant DB: its single Company (what
        CurrentCompanyResolver picks) + the full CRM config (roles, permissions,
        pages, policies — the same data `seed_crm` lays down, minus the company)
        + one admin user. is_superuser lets the owner run everything day one.

        We point the router at the tenant for the whole block (set_current_db),
        so the reused seeder writes into the tenant DB without per-call using=.
        """
        from apps.accounts.models import User, UserProfile
        from apps.authorization.models import RoleGroup
        from apps.companies.models import Company
        from apps.core.management.commands.seed_crm import Command as SeedCrm

        from .db import clear_current_db, set_current_db

        set_current_db(alias)
        try:
            with transaction.atomic(using=alias):
                company = Company.objects.create(name=name, slug=slug, is_active=True)
                SeedCrm().seed_config(company)
                admin_role = RoleGroup.objects.filter(
                    company=company, code="SYSTEM_ADMINS"
                ).first()
                user = User.objects.create_user(
                    email=email, password=password,
                    is_staff=True, is_superuser=True, is_active=True,
                )
                UserProfile.objects.create(
                    user=user, company=company, default_role=admin_role
                )
        finally:
            clear_current_db()


class TenantService:
    @staticmethod
    def set_active(tenant: Tenant, *, active: bool) -> Tenant:
        """The subscription gate. Deactivation blocks the tenant's users at the
        routing middleware; their database is left completely untouched."""
        tenant.is_active = active
        tenant.save(using="default", update_fields=["is_active", "updated_at"])
        return tenant

    @staticmethod
    def update_subscription(tenant: Tenant, *, paid_until=None, notes=None) -> Tenant:
        if paid_until is not None:
            tenant.paid_until = paid_until or None
        if notes is not None:
            tenant.notes = notes
        tenant.save(using="default")
        return tenant

    @staticmethod
    def find_tenant_by_session(session_key: str) -> Tenant | None:
        """Finds which active tenant database contains the given session key."""
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        from .db import set_current_db, clear_current_db, ensure_connection

        # 1. Check if the session exists in the default (control-plane) database.
        try:
            if Session.objects.using("default").filter(
                session_key=session_key,
                expire_date__gt=timezone.now()
            ).exists():
                return None
        except Exception:
            pass

        # 2. Check if the session exists in any of the active tenants' databases.
        for tenant in Tenant.objects.using("default").filter(is_active=True):
            alias = ensure_connection(tenant)
            set_current_db(alias)
            try:
                if Session.objects.filter(
                    session_key=session_key,
                    expire_date__gt=timezone.now()
                ).exists():
                    return tenant
            except Exception:
                pass
            finally:
                clear_current_db()
        return None
