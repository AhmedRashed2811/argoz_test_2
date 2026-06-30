"""Notebook AJAX endpoints. Thin: every endpoint is owner-scoped through
NotebookService — no cross-user access."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .services import NotebookService


@login_required
def note_list(request):
    return JsonResponse(NotebookService.list_payload(request.user))


@login_required
@require_POST
def note_create(request):
    note = NotebookService.create(
        company=request.company,
        owner=request.user,
        title=request.POST.get("title", ""),
        body=request.POST.get("body", ""),
    )
    if note is None:
        return JsonResponse({"ok": False, "error": "Empty note"}, status=400)
    return JsonResponse({"ok": True, "note": NotebookService.serialize(note)})


@login_required
@require_POST
def note_update(request, note_id):
    note = NotebookService.get_note(owner=request.user, note_id=note_id)
    if note is None:
        return JsonResponse({"ok": False}, status=404)
    note = NotebookService.update(
        note=note,
        title=request.POST.get("title", ""),
        body=request.POST.get("body", ""),
    )
    return JsonResponse({"ok": True, "note": NotebookService.serialize(note)})


@login_required
@require_POST
def note_delete(request, note_id):
    note = NotebookService.get_note(owner=request.user, note_id=note_id)
    if note is None:
        return JsonResponse({"ok": False}, status=404)
    NotebookService.delete(note=note)
    return JsonResponse({"ok": True})
