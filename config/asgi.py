"""ASGI config. Routes HTTP to Django and WebSocket to Channels (docs §12, §18)."""
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

django_asgi_app = get_asgi_application()

# Imported after Django setup so app models/consumers are loadable.
from apps.notifications.routing import websocket_urlpatterns as notif_ws  # noqa: E402
from apps.chat.routing import websocket_urlpatterns as chat_ws  # noqa: E402
from apps.tenants.asgi import TenantDBMiddleware  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # TenantDBMiddleware must wrap AuthMiddlewareStack: it points the ORM at
        # the tenant DB so the session/user lookup finds the right user.
        "websocket": AllowedHostsOriginValidator(
            TenantDBMiddleware(AuthMiddlewareStack(URLRouter(notif_ws + chat_ws)))
        ),
    }
)
