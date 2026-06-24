"""Notification views (docs §12, §14): in-app inbox + mark read. Read-only data
plus a single state toggle through the service."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

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
