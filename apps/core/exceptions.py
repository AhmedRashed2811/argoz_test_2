"""Service-layer exceptions. Views translate these to messages/HTTP responses
so business logic never imports django.http (docs §2.1)."""


class ServiceError(Exception):
    """Base for all service-layer failures."""


class PermissionDenied(ServiceError):
    """Raised by the custom authorization layer (docs §4)."""


class PolicyError(ServiceError):
    """Invalid/missing policy configuration (docs §7)."""


class ValidationError(ServiceError):
    """Business validation failure distinct from form field validation."""


class ConcurrencyError(ServiceError):
    """Lost a row lock / lost-update race (docs §17)."""
