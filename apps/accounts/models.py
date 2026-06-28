"""Accounts domain (docs §11): auth identity (§4.1), CRM profile/availability,
sales teams, languages, and brokers. Business permissions stay in the
authorization app — nothing here decides access by role name (§3)."""
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models

from apps.core.models import BaseModel, CompanyOwnedModel


class CRMUserManager(UserManager):
    """email is USERNAME_FIELD, so create_user/superuser must key on email
    while keeping username optional (default UserManager is username-positional)."""

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Login identity. email is the unique business handle; username kept
    optional for Django admin compatibility (docs §11 User)."""

    email = models.EmailField("email address", unique=True)
    phone = models.CharField(max_length=32, blank=True)

    objects = CRMUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self) -> str:
        return self.get_full_name() or self.email


class AvailabilityStatus:
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"
    ON_LEAVE = "ON_LEAVE"
    CHOICES = [
        (AVAILABLE, "Available"),
        (BUSY, "Busy"),
        (OFFLINE, "Offline"),
        (ON_LEAVE, "On leave"),
    ]


class UserProfile(BaseModel, CompanyOwnedModel):
    """CRM profile + availability. default_role is only a permission-bundle
    seed (docs §4.1); effective access is resolved by the authorization app."""

    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="profile"
    )
    job_title = models.CharField(max_length=120, blank=True)
    default_role = models.ForeignKey(
        "authorization.RoleGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_profiles",
    )
    department = models.CharField(max_length=120, blank=True)
    availability_status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.CHOICES,
        default=AvailabilityStatus.AVAILABLE,
    )
    timezone = models.CharField(max_length=64, default="UTC")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    def __str__(self) -> str:
        return f"Profile<{self.user_id}>"


class Language(BaseModel):
    """Arabic default plus future languages (docs §11). Filters the eligible
    salesman pool during automatic distribution (§8.4)."""

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class UserLanguage(BaseModel):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="languages"
    )
    language = models.ForeignKey(
        Language, on_delete=models.CASCADE, related_name="speakers"
    )
    proficiency = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "language"], name="uniq_user_language"
            )
        ]


class Team(BaseModel, CompanyOwnedModel):
    """Sales team root (docs §11). sales_head leads the team; distribution scope
    modes (§8.4) operate over team membership."""

    name = models.CharField(max_length=150)
    sales_head = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_teams",
    )
    region = models.CharField(max_length=120, blank=True)
    order_index = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order_index", "name"]

    def __str__(self) -> str:
        return self.name


class TeamMember(BaseModel):
    """Salesmen and heads membership. max_active_leads caps Round Robin load
    (docs §8.3, §11)."""

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="team_memberships"
    )
    position = models.CharField(max_length=80, blank=True)
    is_available = models.BooleanField(default=True)
    active_from = models.DateField(null=True, blank=True)
    active_to = models.DateField(null=True, blank=True)
    max_active_leads = models.IntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "user"], name="uniq_team_member")
        ]


class BrokerStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BLOCKED = "BLOCKED"
    CHOICES = [
        (ACTIVE, "Active"),
        (INACTIVE, "Inactive"),
        (BLOCKED, "Blocked"),
    ]


class Agency(BaseModel, CompanyOwnedModel):
    """Brokerage agency — the organisation a broker user belongs to (task 1).
    Separate from the individual Broker (the lead's broker_owner), so the leads
    report analysis that keys on Broker is preserved."""

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=150, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=BrokerStatus.CHOICES, default=BrokerStatus.ACTIVE
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Agencies"

    def __str__(self) -> str:
        return self.name


class Broker(BaseModel, CompanyOwnedModel):
    """External broker/intermediary. Broker ownership is kept strictly separate
    from internal salesman assignment (docs §8.5)."""

    linked_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="broker_profile",
    )
    agency = models.ForeignKey(
        "accounts.Agency", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="brokers",
    )
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    company_name = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=150, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    leads_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=BrokerStatus.CHOICES, default=BrokerStatus.ACTIVE
    )
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name
