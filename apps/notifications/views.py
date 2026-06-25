"""Notification views (docs §12, §14): in-app inbox + mark read. Read-only data
plus a single state toggle through the service."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notification
from .services import NotificationService


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related("notification_type").order_by("-created_at")[:100]
    return render(request, "notifications/notification_list.html", {
        "notifications": notifications,
    })


@login_required
def mark_read(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    NotificationService.mark_read(notification=notif)
    return redirect("notifications:list")


# ── AJAX API for the header notification panel (read-only + state toggles) ──
def _serialize(n):
    return {
        "id": str(n.id),
        "title": n.title,
        "body": n.body,
        "type": n.notification_type.name if n.notification_type else "",
        "code": n.notification_type.code if n.notification_type else "",
        "priority": n.priority,
        "related_type": n.related_type,
        "created_at": timezone.localtime(n.created_at).isoformat(),
        "is_read": n.is_read,
    }


@login_required
def notification_api_list(request):
    qs = Notification.objects.filter(
        recipient=request.user
    ).select_related("notification_type").order_by("-created_at")[:50]
    items = [_serialize(n) for n in qs]
    unread = sum(1 for item in items if not item["is_read"])
    return JsonResponse({"items": items, "unread": unread})


@login_required
@require_POST
def notification_api_mark_read(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    NotificationService.mark_read(notification=notif)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def notification_api_mark_all_read(request):
    count = NotificationService.mark_all_read(recipient=request.user)
    return JsonResponse({"ok": True, "marked": count})
