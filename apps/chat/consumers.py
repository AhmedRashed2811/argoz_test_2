"""WebSocket consumer for direct chat. Each authenticated user joins their own
group (chat_user_<id>); sent messages and read-receipts fan out to both
participants' groups so every open tab updates without a refresh.

Stays thin — DB work is delegated to ChatService via sync_to_async."""
from __future__ import annotations

import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.tenants.db import current_scope


def _chat_group(user_id) -> str:
    # Tenant-scoped: the channel layer is one shared Redis, and user ids repeat
    # across tenant DBs — an un-scoped group name would fan a message out to the
    # same-id user in every other tenant.
    return f"chat_user_{current_scope()}_{user_id}"


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close()
            return
        self.user = user
        self.group = _chat_group(user.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except (ValueError, TypeError):
            return
        action = data.get("action")
        if action == "send":
            await self._handle_send(data)
        elif action == "read":
            await self._handle_read(data)

    async def _handle_send(self, data):
        body = (data.get("body") or "").strip()
        convo_id = data.get("conversation_id")
        if not body or not convo_id:
            return
        result = await sync_to_async(self._save_message)(convo_id, body)
        if not result:
            return
        payload, recipient_ids = result
        for uid in recipient_ids:
            await self.channel_layer.group_send(
                _chat_group(uid),
                {"type": "chat.message", "message": payload},
            )

    async def _handle_read(self, data):
        convo_id = data.get("conversation_id")
        if not convo_id:
            return
        recipient_ids = await sync_to_async(self._mark_read)(convo_id)
        if recipient_ids is None:
            return
        for uid in recipient_ids:
            await self.channel_layer.group_send(
                _chat_group(uid),
                {
                    "type": "chat.read",
                    "conversation_id": str(convo_id),
                    "reader_id": str(self.user.id),
                },
            )

    # ── sync DB helpers (run via sync_to_async) ──────────────────────────
    def _save_message(self, convo_id, body):
        from .services import ChatService

        convo = ChatService.get_conversation(user=self.user, conversation_id=convo_id)
        if convo is None:
            return None
        msg = ChatService.send_message(
            conversation=convo, sender=self.user, body=body
        )
        payload = ChatService.serialize_message(msg)
        recipient_ids = list(
            convo.participants.values_list("id", flat=True)
        )
        return payload, recipient_ids

    def _mark_read(self, convo_id):
        from .services import ChatService

        convo = ChatService.get_conversation(user=self.user, conversation_id=convo_id)
        if convo is None:
            return None
        ChatService.mark_read(conversation=convo, reader=self.user)
        return list(convo.participants.values_list("id", flat=True))

    # ── group_send handlers ──────────────────────────────────────────────
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(
            {"type": "message", "message": event["message"]}
        ))

    async def chat_read(self, event):
        await self.send(text_data=json.dumps({
            "type": "read",
            "conversation_id": event["conversation_id"],
            "reader_id": event["reader_id"],
        }))
