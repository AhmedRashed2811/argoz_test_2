"""Webhook receive endpoint (docs §13.2). This is an integration webhook, not a
frontend REST API (allowed by §1.1). Thin: authenticate, store, queue async
processing, return JSON. Idempotency/dedupe live in the service."""
from __future__ import annotations

import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.authorization.decorators import crm_permission_required
from apps.core.exceptions import ValidationError

from .models import WebhookEndpoint
from .services import WebhookReceiverService
from .setup_service import IntegrationSetupService


class WebhookEndpointForm(forms.Form):
    name = forms.CharField(max_length=120)
    provider_code = forms.ChoiceField(
        choices=[("MAKE", "Make"), ("ZAPIER", "Zapier")]
    )
    default_source_code = forms.CharField(max_length=40, initial="CAMPAIGN")


@login_required
@crm_permission_required("integrations.webhooks.manage")
def webhook_list(request):
    endpoints = WebhookEndpoint.objects.filter(company=request.company)
    rows = [{"ep": ep, "url": IntegrationSetupService.endpoint_url(ep)}
            for ep in endpoints]
    return render(request, "integrations/webhook_list.html", {"rows": rows})


@login_required
@crm_permission_required("integrations.webhooks.manage")
def webhook_create(request):
    form = WebhookEndpointForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        IntegrationSetupService.create_endpoint(
            company=request.company, provider_code=d["provider_code"],
            name=d["name"], actor=request.user,
            default_source_code=d["default_source_code"],
        )
        messages.success(request, "Webhook endpoint created. Copy the URL into Make/Zapier.")
        return redirect("integrations:webhook_list")
    return render(request, "form.html", {"title": "New webhook endpoint", "form": form})


@csrf_exempt
@require_POST
def receive_webhook(request, endpoint_uuid):
    token = request.headers.get("X-Webhook-Token") or request.GET.get("token", "")
    try:
        endpoint = WebhookReceiverService.authenticate(
            endpoint_uuid=endpoint_uuid, token=token
        )
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=401)

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    external_event_id = str(payload.get("event_id", "") or payload.get("id", ""))
    event = WebhookReceiverService.receive(
        endpoint=endpoint, payload=payload, external_event_id=external_event_id
    )

    # Process asynchronously so the provider gets a fast 202 (docs §12.1).
    from .tasks import process_webhook_event

    process_webhook_event.delay(str(event.id))
    return JsonResponse({"status": "accepted", "event_id": str(event.id)}, status=202)
