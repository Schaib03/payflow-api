import functools
import json
import random

import requests
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from core import metrics
from webhooks.models import Event, WebhookDelivery
from webhooks.signing import SIGNATURE_HEADER, build_header


def emit_event(merchant, event_type, data):
    from webhooks.tasks import deliver_webhook

    event = Event.objects.create(
        merchant=merchant,
        type=event_type,
        data=json.loads(json.dumps(data, cls=DjangoJSONEncoder)),
    )
    endpoints = [
        endpoint
        for endpoint in merchant.webhook_endpoints.filter(is_active=True)
        if endpoint.accepts(event_type)
    ]
    deliveries = WebhookDelivery.objects.bulk_create(
        WebhookDelivery(event=event, endpoint=endpoint) for endpoint in endpoints
    )
    # Enqueue after commit: a rolled back payment must not send a webhook.
    for delivery in deliveries:
        transaction.on_commit(functools.partial(deliver_webhook.delay, str(delivery.id)))
    return event


def build_payload(event):
    body = {
        "id": str(event.id),
        "type": event.type,
        "created_at": event.created_at.isoformat(),
        "data": event.data,
    }
    return json.dumps(body, separators=(",", ":")).encode()


def backoff_seconds(attempt):
    delay = min(
        settings.WEBHOOK_BACKOFF_BASE_SECONDS * 2 ** (attempt - 1),
        settings.WEBHOOK_BACKOFF_MAX_SECONDS,
    )
    return delay + random.randint(0, delay // 10)


def attempt_delivery(delivery):
    endpoint = delivery.endpoint
    payload = build_payload(delivery.event)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "PayFlow-Webhooks/1.0",
        "PayFlow-Event-Id": str(delivery.event_id),
        "PayFlow-Delivery-Id": str(delivery.id),
        SIGNATURE_HEADER: build_header(endpoint.secret, payload),
    }

    delivery.attempts += 1
    try:
        response = requests.post(
            endpoint.url,
            data=payload,
            headers=headers,
            timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        delivered = False
        delivery.last_status_code = None
        delivery.last_error = f"{type(exc).__name__}: {exc}"[:500]
    else:
        delivered = 200 <= response.status_code < 300
        delivery.last_status_code = response.status_code
        delivery.last_error = "" if delivered else f"HTTP {response.status_code}"

    metrics.WEBHOOK_DELIVERIES.labels("success" if delivered else "failure").inc()
    if delivered:
        delivery.status = WebhookDelivery.Status.SUCCEEDED
        delivery.delivered_at = timezone.now()
        delivery.next_attempt_at = None
    delivery.save()
    return delivered
