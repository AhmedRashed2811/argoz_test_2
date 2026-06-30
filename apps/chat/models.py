"""Direct (1-to-1) chat between any two company users (docs §11 pattern).

Fields/relations only — all behaviour lives in services.py. A Conversation is a
direct thread between exactly two participants; Message rows carry a single
``is_read`` flag (the recipient's read state, since threads are 1-to-1)."""
from django.db import models

from apps.core.models import BaseModel, CompanyOwnedModel


class Conversation(BaseModel, CompanyOwnedModel):
    participants = models.ManyToManyField(
        "accounts.User", related_name="conversations"
    )
    # Denormalised so the conversation list can sort without scanning messages.
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    def other_participant(self, user):
        return self.participants.exclude(pk=user.pk).first()


class Message(BaseModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="sent_messages"
    )
    body = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]


def _attachment_path(instance, filename):
    """Date-bucketed, uuid-named path: avoids hot directories and collisions."""
    import uuid
    from django.utils import timezone

    ext = (filename.rsplit(".", 1)[-1] or "bin").lower()[:8]
    now = timezone.now()
    return f"chat/{now:%Y/%m}/{uuid.uuid4().hex}.{ext}"


class Attachment(BaseModel):
    """A file or image carried by a Message. Images are stored re-encoded to
    WebP (capped dimensions) plus a small thumbnail so inline rendering is fast
    and cheap; other files are stored as-is. Original name/size kept for display."""

    KIND_IMAGE = "image"
    KIND_FILE = "file"

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="attachments"
    )
    kind = models.CharField(max_length=10, default=KIND_FILE)
    file = models.FileField(upload_to=_attachment_path)
    thumbnail = models.ImageField(upload_to=_attachment_path, null=True, blank=True)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveIntegerField(default=0)  # bytes of the stored file
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
