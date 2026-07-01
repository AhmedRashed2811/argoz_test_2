"""SaaS control-plane registry. Lives ONLY in the `default` database (the
control plane); never queried from inside a tenant request. One row per paying
company; each row points at that company's own MariaDB database. Activation is
the manual-cash subscription gate: is_active=False blocks the tenant's users at
the routing middleware without touching any of their data."""
from django.db import models


class Tenant(models.Model):
    name = models.CharField(max_length=255, help_text="Company display name")
    slug = models.SlugField(
        max_length=63, unique=True,
        help_text="URL segment and DB key, e.g. 'acme' -> /t/acme/",
    )
    # Connection to this tenant's own database. Defaulted from env at creation
    # (see TenantProvisioningService); stored per-row so tenants can later live
    # on different servers without code changes.
    db_name = models.CharField(max_length=64)
    db_host = models.CharField(max_length=255, default="127.0.0.1")
    db_port = models.CharField(max_length=8, default="3306")
    db_user = models.CharField(max_length=64, default="root")
    # ponytail: plaintext, same trust level as .env; move to a secrets store
    # before this leaves a single-operator setup.
    db_password = models.CharField(max_length=255, blank=True, default="")

    # Subscription gate — manual cash, no billing integration.
    is_active = models.BooleanField(
        default=True, help_text="Uncheck to suspend access; data is preserved."
    )
    paid_until = models.DateField(
        null=True, blank=True, help_text="Optional: when the current paid period ends."
    )
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"

    @property
    def db_alias(self) -> str:
        """Stable Django connection alias for this tenant's database."""
        return f"tenant_{self.slug}"

    def connection_config(self) -> dict:
        """settings.DATABASES-style dict for this tenant's MariaDB database."""
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": self.db_name,
            "USER": self.db_user,
            "PASSWORD": self.db_password,
            "HOST": self.db_host,
            "PORT": self.db_port,
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            # NOT atomic-per-request: async views (e.g. notifications SSE) are
            # exempted via @transaction.non_atomic_requests only for the static
            # `default` alias, never these dynamic tenant aliases — so leaving
            # this True makes Django try to wrap async views and crash. Services
            # that need atomicity already use explicit transaction.atomic().
            # ponytail: revisit if a tenant write path needs request-level atomicity.
            "ATOMIC_REQUESTS": False,
            "AUTOCOMMIT": True,
            "CONN_MAX_AGE": 0,
            "CONN_HEALTH_CHECKS": False,
            "TIME_ZONE": None,
            "TEST": {},
        }
