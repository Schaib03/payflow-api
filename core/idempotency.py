"""Idempotency-Key support for POST endpoints.

The first request with a given key claims it (unique row per merchant + key),
runs, and stores its response. A retry with the same key and the same body gets
the stored response back without running the view again. The same key with a
different body is a client bug and gets a 422.

Responses are only stored when the request changed state: 2xx, and 402 because
a declined card still creates a failed payment. For validation errors and
server errors the key is released so the client can fix the request and retry.
"""

import functools
import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter
from rest_framework import exceptions, status
from rest_framework.response import Response

from core.models import IdempotencyKey

HEADER = "Idempotency-Key"
REPLAY_HEADER = "Idempotent-Replayed"
MAX_KEY_LENGTH = 255

IDEMPOTENCY_PARAMETER = OpenApiParameter(
    HEADER,
    str,
    OpenApiParameter.HEADER,
    required=False,
    description="Unique key (e.g. a UUID) that makes retries of this request safe.",
)


class IdempotencyKeyReused(exceptions.APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "idempotency_key_reused"
    default_detail = "This Idempotency-Key was already used with a different request."
    error_type = "idempotency_error"


class IdempotencyKeyInProgress(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "idempotency_key_in_progress"
    default_detail = "A request with this Idempotency-Key is still being processed."
    error_type = "idempotency_error"


def request_fingerprint(request):
    body = json.dumps(request.data, sort_keys=True, separators=(",", ":"), cls=DjangoJSONEncoder)
    raw = f"{request.method}\n{request.path}\n{body}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _should_store(response):
    return 200 <= response.status_code < 300 or response.status_code == 402


def _jsonable(data):
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def _claim(merchant, key, fingerprint):
    """Insert the key, or return the existing row. The unique constraint settles races."""
    try:
        with transaction.atomic():
            record = IdempotencyKey.objects.create(
                merchant=merchant, key=key, request_fingerprint=fingerprint
            )
            return record, True
    except IntegrityError:
        record = IdempotencyKey.objects.get(merchant=merchant, key=key)

    ttl = timedelta(hours=settings.IDEMPOTENCY_KEY_TTL_HOURS)
    if record.created_at < timezone.now() - ttl:
        record.delete()
        return _claim(merchant, key, fingerprint)
    return record, False


def idempotent(view_method):
    """Decorator for APIView.post (runs after authentication)."""

    @functools.wraps(view_method)
    def wrapper(view, request, *args, **kwargs):
        key = request.headers.get(HEADER)
        if key is None:
            return view_method(view, request, *args, **kwargs)

        key = key.strip()
        if not key or len(key) > MAX_KEY_LENGTH:
            raise exceptions.ValidationError(
                {HEADER: [f"Must be between 1 and {MAX_KEY_LENGTH} characters."]}
            )

        fingerprint = request_fingerprint(request)
        record, created = _claim(request.user, key, fingerprint)

        if not created:
            if record.request_fingerprint != fingerprint:
                raise IdempotencyKeyReused()
            if record.status == IdempotencyKey.Status.IN_PROGRESS:
                raise IdempotencyKeyInProgress()
            response = Response(record.response_body, status=record.response_status)
            response[REPLAY_HEADER] = "true"
            return response

        try:
            response = view_method(view, request, *args, **kwargs)
        except Exception:
            record.delete()
            raise

        if _should_store(response):
            record.status = IdempotencyKey.Status.COMPLETED
            record.response_status = response.status_code
            record.response_body = _jsonable(response.data)
            record.save(update_fields=["status", "response_status", "response_body"])
        else:
            record.delete()
        return response

    return wrapper
