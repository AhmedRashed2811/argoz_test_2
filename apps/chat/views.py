"""Chat AJAX endpoints (docs §14). Thin: read-only payloads + conversation
open; message sending happens over the WebSocket. Every endpoint is
participant-scoped through ChatService — no cross-user access."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .services import ChatService


@login_required
def chat_list(request):
    return JsonResponse(ChatService.list_payload(request.user))


@login_required
def chat_users(request):
    users = [
        ChatService._user_brief(u)
        for u in ChatService.directory(company=request.company, user=request.user)
    ]
    return JsonResponse({"users": users})


@login_required
@require_POST
def chat_open(request):
    convo = ChatService.get_or_create_direct(
        company=request.company,
        user=request.user,
        other_id=request.POST.get("user_id"),
    )
    if convo is None:
        return JsonResponse({"ok": False, "error": "User not found"}, status=404)
    return JsonResponse(
        {"ok": True, **ChatService.history_payload(conversation=convo, viewer=request.user)}
    )


@login_required
def chat_history(request, conversation_id):
    convo = ChatService.get_conversation(
        user=request.user, conversation_id=conversation_id
    )
    if convo is None:
        return JsonResponse({"ok": False}, status=404)
    ChatService.mark_read(conversation=convo, reader=request.user)
    return JsonResponse(
        {"ok": True, **ChatService.history_payload(conversation=convo, viewer=request.user)}
    )


@login_required
@require_POST
def chat_upload(request):
    convo = ChatService.get_conversation(
        user=request.user, conversation_id=request.POST.get("conversation_id")
    )
    if convo is None:
        return JsonResponse({"ok": False}, status=404)
    msg = ChatService.create_with_attachments(
        conversation=convo, sender=request.user,
        body=request.POST.get("body", ""), files=request.FILES.getlist("files"),
    )
    if msg is None:
        return JsonResponse({"ok": False, "error": "Nothing to send"}, status=400)
    ChatService.fanout(msg)            # appears live for both, like a text message
    return JsonResponse({"ok": True, "message": ChatService.serialize_message(msg)})


@login_required
@require_POST
def chat_mark_read(request, conversation_id):
    convo = ChatService.get_conversation(
        user=request.user, conversation_id=conversation_id
    )
    if convo is None:
        return JsonResponse({"ok": False}, status=404)
    count = ChatService.mark_read(conversation=convo, reader=request.user)
    return JsonResponse({"ok": True, "marked": count})
