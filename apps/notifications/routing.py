"""WebSocket routing for realtime notifications (docs §12)."""
from django.urls import path

from .consumers import NotificationConsumer

websocket_urlpatterns = [
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
