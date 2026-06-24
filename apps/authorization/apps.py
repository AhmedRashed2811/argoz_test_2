from django.apps import AppConfig


class AuthorizationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.authorization"

    def ready(self):
        from . import signals  # noqa: F401  (connects cache-invalidation hooks)
