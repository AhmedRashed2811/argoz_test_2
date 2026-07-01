"""Base settings shared across environments. Env-driven so management commands
run without a live DB/Redis. See docs §2.2."""
import os
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())

# config/settings/base.py -> project root is BASE_DIR; apps live under apps/
APPS_DIR = BASE_DIR / "apps"

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "channels",
    "django_extensions",
]

# Order matters: core/companies first (base models, resolver), then domains.
LOCAL_APPS = [
    "apps.core",
    "apps.tenants",
    "apps.companies",
    "apps.accounts",
    "apps.authorization",
    "apps.audit",
    "apps.policies",
    "apps.leads",
    "apps.distribution",
    "apps.marketing",
    "apps.finance",
    "apps.notifications",
    "apps.chat",
    "apps.notebook",
    "apps.integrations",
    "apps.reports",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Per-DB tenant routing must run before sessions/auth so those lookups hit
    # the tenant's database (SaaS DB-per-tenant, /t/<slug>/).
    "apps.tenants.middleware.TenantRoutingMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # CRM cross-cutting context: resolves request.company and request_meta.
    "apps.companies.middleware.CurrentCompanyMiddleware",
    "apps.audit.middleware.RequestMetaMiddleware",
    # Replays cached responses for repeated idempotency keys (double-submit /
    # network-retry protection). Last so it wraps the resolved view.
    "apps.core.middleware.IdempotencyMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.authorization.context_processors.nav_menu",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# MariaDB "argoz" per docs §2.2. URL form via dj-database-url, fallback to sqlite
# so check/makemigrations work on a fresh machine without MySQL running.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("MYSQL_DATABASE", default="argoz"),
        "USER": config("MYSQL_USER", default="root"),
        "PASSWORD": config("MYSQL_PASSWORD", default=""),
        "HOST": config("MYSQL_HOST", default="127.0.0.1"),
        "PORT": config("MYSQL_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        # Wrap every request in a transaction so a mid-write network drop can
        # never leave partial/corrupt rows across related models.
        "ATOMIC_REQUESTS": True,
    }
}

AUTH_USER_MODEL = "accounts.User"

# DB-per-tenant routing: queries go to the request's tenant DB, falling back to
# `default` (the control plane) when no tenant is active. See apps.tenants.
DATABASE_ROUTERS = ["apps.tenants.routers.TenantRouter"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = config("TIME_ZONE", default="Africa/Cairo")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/"

# --- Redis / Celery / Channels (docs §2.2, §12) ---
REDIS_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=False, cast=bool)
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat periodic jobs (docs §12.1). Cadences are conservative defaults.
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    # SLA expiry and its warning reminder are both eta-scheduled per instance
    # (apps.leads.tasks.expire_sla_instance / send_sla_reminder) at the moment
    # the SLA opens — no more minute-by-minute polling for either.
    "send_due_reminders": {
        "task": "apps.leads.tasks.send_due_reminders",
        "schedule": 60.0,
    },
    "retry_failed_webhooks": {
        "task": "apps.integrations.tasks.retry_failed_webhooks",
        "schedule": 600.0,  # every 10 min (docs: 5-15 min)
    },
    "recalculate_campaign_metrics": {
        "task": "apps.marketing.tasks.recalculate_campaign_metrics",
        "schedule": 3600.0,  # hourly reconciliation (docs §12.1)
    },
    # Task 16c — prune old notifications per company policy (daily 02:00).
    "cleanup_old_notifications": {
        "task": "apps.notifications.tasks.cleanup_old_notifications",
        "schedule": crontab(hour=2, minute=0),
    },
    # Task 16d — daily task-reminder emails to sales / heads (daily 07:00;
    # the task itself skips the company's configured weekend day(s)).
    "send_daily_task_emails": {
        "task": "apps.notifications.tasks.send_daily_task_emails",
        "schedule": crontab(hour=7, minute=0),
    },
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("CACHE_URL", default=REDIS_URL),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [config("CHANNELS_REDIS_URL", default=REDIS_URL)]},
    }
}

EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=465, cast=int)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="crm@argoz.local")

WEBHOOK_BASE_URL = config("WEBHOOK_BASE_URL", default="http://localhost:8000")
