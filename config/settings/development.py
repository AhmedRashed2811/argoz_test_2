"""Development overrides. Defaults to sqlite so a fresh checkout can run
migrate/check without MariaDB. Set USE_MYSQL=1 to use the docs §2.2 MariaDB."""
from decouple import config

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = True
ALLOWED_HOSTS = ["*"]

if not config("USE_MYSQL", default=False, cast=bool):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "ATOMIC_REQUESTS": True,
        }
    }

CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=True, cast=bool)

# Dev runs without Redis by default; set USE_REDIS=1 to exercise the real stack.
if not config("USE_REDIS", default=False, cast=bool):
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }
