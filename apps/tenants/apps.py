from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenants"
    label = "tenants"
    verbose_name = "Tenants (SaaS control plane)"

    def ready(self):
        from .db import install_tenant_atomic

        install_tenant_atomic()
