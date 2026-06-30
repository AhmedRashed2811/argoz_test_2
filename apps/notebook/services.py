"""Notebook business logic (views stay thin, logic lives here).

Every query is owner-scoped: a user only ever sees and edits their own notes.
Serialization is centralised so all AJAX views emit identical shapes."""
from __future__ import annotations

from django.utils import timezone

from .models import Note

_PREVIEW_LEN = 140


class NotebookService:
    # ── Queries ──────────────────────────────────────────────────────────
    @staticmethod
    def notes_for(owner):
        return Note.objects.filter(owner=owner)

    @staticmethod
    def get_note(*, owner, note_id) -> Note | None:
        # owner= filter is the security boundary: other users' notes return None.
        return Note.objects.filter(pk=note_id, owner=owner).first()

    # ── Mutations ────────────────────────────────────────────────────────
    @staticmethod
    def create(*, company, owner, title: str, body: str) -> Note | None:
        title, body = (title or "").strip()[:200], (body or "").strip()
        if not title and not body:
            return None
        return Note.objects.create(
            company=company, owner=owner, title=title, body=body
        )

    @staticmethod
    def update(*, note: Note, title: str, body: str) -> Note:
        note.title = (title or "").strip()[:200]
        note.body = (body or "").strip()
        note.save(update_fields=["title", "body", "updated_at"])
        return note

    @staticmethod
    def delete(*, note: Note) -> None:
        note.delete()

    # ── Serialization ────────────────────────────────────────────────────
    @staticmethod
    def serialize(note: Note) -> dict:
        return {
            "id": str(note.id),
            "title": note.title,
            "body": note.body,
            "preview": (note.body or "")[:_PREVIEW_LEN],
            "updated_at": timezone.localtime(note.updated_at).isoformat(),
        }

    @staticmethod
    def list_payload(owner) -> dict:
        return {
            "notes": [
                NotebookService.serialize(n)
                for n in NotebookService.notes_for(owner)
            ]
        }
