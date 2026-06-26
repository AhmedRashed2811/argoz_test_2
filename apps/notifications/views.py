"""Notification views (docs §12, §14): in-app inbox + mark read. Read-only data
plus a single state toggle through the service."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notification
from .services import NotificationService



@login_required
def mark_read(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    NotificationService.mark_read(notification=notif)
    return redirect("notifications:list")


# ── AJAX API for the header notification panel (read-only + state toggles) ──
@login_required
def notification_api_list(request):
    data = NotificationService.get_api_list(request.user)
    return JsonResponse(data)



@login_required
@require_POST
def notification_api_mark_read(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    NotificationService.mark_read(notification=notif)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def notification_api_delete(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    NotificationService.delete(notification=notif)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def notification_api_mark_all_read(request):
    count = NotificationService.mark_all_read(recipient=request.user)
    return JsonResponse({"ok": True, "marked": count})


async def notification_sse(request):
    from asgiref.sync import sync_to_async
    from django.contrib.auth import get_user
    user = await sync_to_async(get_user)(request)
    if not user.is_authenticated:
        return HttpResponseForbidden()
    response = StreamingHttpResponse(NotificationService.sse_stream(user), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
