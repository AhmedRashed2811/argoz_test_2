"""Chat business logic (docs §15: views/consumers stay thin, logic lives here).

All access control is participant-scoped: a user only ever sees conversations
they belong to. Serialization is centralised so the AJAX views and the
WebSocket consumer emit identical shapes."""
from __future__ import annotations

from io import BytesIO

from django.core.files.base import ContentFile
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User

from .models import Attachment, Conversation, Message

# Upload guardrails (trust boundary — enforced server-side, never just in JS).
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MB per file
MAX_FILES_PER_MESSAGE = 10
_IMAGE_FULL_MAX = (1920, 1920)
_IMAGE_THUMB_MAX = (360, 360)


class ChatService:
    # ── Queries ──────────────────────────────────────────────────────────
    @staticmethod
    def conversations_for(user):
        return (
            user.conversations.all()
            .prefetch_related("participants", "participants__profile")
            .order_by("-last_message_at", "-created_at")
        )

    @staticmethod
    def get_conversation(*, user, conversation_id) -> Conversation | None:
        # participants= filter is the security boundary: non-members get None.
        return (
            Conversation.objects.filter(pk=conversation_id, participants=user)
            .prefetch_related("participants", "participants__profile")
            .first()
        )

    @staticmethod
    def get_or_create_direct(*, company, user, other_id) -> Conversation | None:
        other = User.objects.filter(
            pk=other_id, profile__company=company
        ).first()
        if other is None or other.pk == user.pk:
            return None
        existing = (
            Conversation.objects.filter(participants=user)
            .filter(participants=other)
            .first()
        )
        if existing:
            return existing
        convo = Conversation.objects.create(company=company)
        convo.participants.add(user, other)
        return convo

    @staticmethod
    def directory(*, company, user):
        """Company users available to start a chat with (everyone but self)."""
        return (
            User.objects.filter(profile__company=company, is_active=True)
            .exclude(pk=user.pk)
            .select_related("profile")
            .order_by("first_name", "last_name", "email")
        )

    @staticmethod
    def unread_total(user) -> int:
        return Message.objects.filter(
            conversation__participants=user, is_read=False
        ).exclude(sender=user).count()

    # ── Mutations ────────────────────────────────────────────────────────
    @staticmethod
    def send_message(*, conversation: Conversation, sender, body: str) -> Message:
        msg = Message.objects.create(
            conversation=conversation, sender=sender, body=body.strip()
        )
        Conversation.objects.filter(pk=conversation.pk).update(
            last_message_at=msg.created_at
        )
        return msg

    @staticmethod
    def create_with_attachments(*, conversation: Conversation, sender, body: str,
                                files) -> Message | None:
        """Persist a message plus its uploaded files. Images are re-encoded to
        WebP (full + thumbnail); other files stored verbatim. Returns None if
        there's nothing to send (no body and no valid files)."""
        files = list(files or [])[:MAX_FILES_PER_MESSAGE]
        body = (body or "").strip()
        if not body and not files:
            return None
        msg = Message.objects.create(conversation=conversation, sender=sender, body=body)
        created_any = False
        for up in files:
            if up.size and up.size > MAX_ATTACHMENT_BYTES:
                continue
            ChatService._store_attachment(msg, up)
            created_any = True
        if not body and not created_any:
            msg.delete()
            return None
        Conversation.objects.filter(pk=conversation.pk).update(
            last_message_at=msg.created_at
        )
        return msg

    @staticmethod
    def _store_attachment(message: Message, up) -> Attachment:
        full_io, thumb_io, width, height = ChatService._encode_image(up)
        if full_io is not None:                       # it's an image
            stem = (up.name.rsplit(".", 1)[0] or "image")[:80]
            att = Attachment(
                message=message, kind=Attachment.KIND_IMAGE,
                original_name=up.name[:255], content_type="image/webp",
                width=width, height=height,
            )
            att.file.save(f"{stem}.webp", ContentFile(full_io.getvalue()), save=False)
            att.thumbnail.save(f"{stem}_t.webp", ContentFile(thumb_io.getvalue()), save=False)
            att.size = att.file.size
            att.save()
            return att
        # Non-image: store as-is, no thumbnail.
        att = Attachment(
            message=message, kind=Attachment.KIND_FILE,
            original_name=up.name[:255],
            content_type=getattr(up, "content_type", "") or "",
            size=up.size or 0,
        )
        att.file.save(up.name[:120], up, save=False)
        att.save()
        return att

    @staticmethod
    def _encode_image(up):
        """Return (full_webp_io, thumb_webp_io, width, height) for images, or
        (None, None, None, None) when the upload isn't a decodable image.
        One decode, two downscales — keeps peak memory bounded."""
        try:
            from PIL import Image, ImageOps
        except Exception:
            return None, None, None, None
        try:
            up.seek(0)
            im = Image.open(up)
            im.draft("RGB", _IMAGE_FULL_MAX)          # cheap pre-scale for JPEG
            im = ImageOps.exif_transpose(im)
            has_alpha = im.mode in ("RGBA", "LA", "P")
            im = im.convert("RGBA" if has_alpha else "RGB")
        except Exception:
            up.seek(0)
            return None, None, None, None

        full = im.copy(); full.thumbnail(_IMAGE_FULL_MAX, Image.LANCZOS)
        thumb = im.copy(); thumb.thumbnail(_IMAGE_THUMB_MAX, Image.LANCZOS)

        def _webp(img):
            out = BytesIO()
            img.save(out, format="WEBP", quality=80, method=6)
            return out

        return _webp(full), _webp(thumb), full.width, full.height

    @staticmethod
    def fanout(message: Message) -> None:
        """Push a message to both participants' WebSocket groups from sync code
        (used by the HTTP upload view; the consumer fans out its own sends)."""
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return
        payload = ChatService.serialize_message(message)
        for uid in message.conversation.participants.values_list("id", flat=True):
            async_to_sync(layer.group_send)(
                f"chat_user_{uid}", {"type": "chat.message", "message": payload}
            )

    @staticmethod
    def mark_read(*, conversation: Conversation, reader) -> int:
        """Mark the other party's messages as read for *reader*. Returns count."""
        return (
            conversation.messages.filter(is_read=False)
            .exclude(sender=reader)
            .update(is_read=True)
        )

    # ── Serialization ────────────────────────────────────────────────────
    @staticmethod
    def _user_brief(u) -> dict:
        initials = ((u.first_name[:1] + u.last_name[:1]) or u.email[:1]).upper()
        return {
            "id": str(u.pk),
            "name": u.get_full_name() or u.email,
            "initials": initials,
        }

    @staticmethod
    def _serialize_attachment(a: Attachment) -> dict:
        return {
            "id": str(a.id),
            "kind": a.kind,
            "url": a.file.url if a.file else "",
            "thumb_url": a.thumbnail.url if a.thumbnail else "",
            "name": a.original_name,
            "size": a.size,
            "width": a.width,
            "height": a.height,
        }

    @staticmethod
    def serialize_message(m: Message) -> dict:
        atts = [ChatService._serialize_attachment(a) for a in m.attachments.all()]
        return {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "sender": ChatService._user_brief(m.sender),
            "body": m.body,
            "attachments": atts,
            "is_read": m.is_read,
            "created_at": timezone.localtime(m.created_at).isoformat(),
        }

    @staticmethod
    def _preview_text(msg: Message) -> str:
        if msg.body:
            return msg.body
        att = msg.attachments.all()[:1]
        if att:
            a = att[0]
            return "📷 Photo" if a.kind == Attachment.KIND_IMAGE else f"📎 {a.original_name}"
        return ""

    @staticmethod
    def serialize_conversation(convo: Conversation, *, viewer) -> dict:
        other = convo.other_participant(viewer)
        last = convo.messages.order_by("-created_at").first()
        unread = (
            convo.messages.filter(is_read=False).exclude(sender=viewer).count()
        )
        return {
            "id": str(convo.id),
            "other": ChatService._user_brief(other) if other else None,
            "last_message": (
                {
                    "body": ChatService._preview_text(last),
                    "from_me": last.sender_id == viewer.pk,
                    "created_at": timezone.localtime(last.created_at).isoformat(),
                }
                if last
                else None
            ),
            "unread": unread,
        }

    @staticmethod
    def list_payload(user) -> dict:
        convos = [
            ChatService.serialize_conversation(c, viewer=user)
            for c in ChatService.conversations_for(user)
        ]
        # Hide empty conversations that were created but never used.
        convos = [c for c in convos if c["last_message"]]
        return {
            "conversations": convos,
            "unread_total": ChatService.unread_total(user),
        }

    @staticmethod
    def history_payload(*, conversation: Conversation, viewer) -> dict:
        msgs = [
            ChatService.serialize_message(m)
            for m in conversation.messages.select_related("sender")
            .prefetch_related("attachments").all()
        ]
        return {
            "conversation": ChatService.serialize_conversation(
                conversation, viewer=viewer
            ),
            "messages": msgs,
        }
