"""WebSocket routing for direct chat (mirrors notifications.routing)."""
from django.urls import path

from .consumers import ChatConsumer

websocket_urlpatterns = [
    path("ws/chat/", ChatConsumer.as_asgi()),
]
