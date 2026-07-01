"""WebSocket consumer for realtime notifications (docs §12). Each authenticated
user joins their own group; fanout_notification pushes into it."""
from __future__ import annotations

import json

from channels.generic.websocket import AsyncWebsocketConsumer

from apps.tenants.db import current_scope


def notif_group(user_id) -> str:
    # Tenant-scoped: shared Redis channel layer + per-tenant repeating user ids
    # (see chat.consumers._chat_group).
    return f"notifications_{current_scope()}_{user_id}"


def sse_channel(user_id) -> str:
    return f"sse_notif:{current_scope()}:{user_id}"


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close()
            return
        self.group = notif_group(user.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def notify(self, event):
        await self.send(text_data=json.dumps(event["payload"]))
