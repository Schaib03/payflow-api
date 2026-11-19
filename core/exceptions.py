import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

ERROR_TYPES = {
    400: "invalid_request_error",
    401: "authentication_error",
    402: "card_error",
    403: "permission_error",
    404: "not_found_error",
    405: "invalid_request_error",
    409: "conflict_error",
    415: "invalid_request_error",
    422: "idempotency_error",
    429: "rate_limit_error",
}


def error_body(error_type, code, message, **extra):
    return {"error": {"type": error_type, "code": code, "message": message, **extra}}


class InvalidRequest(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid_request"
    default_detail = "The request is invalid."


class Conflict(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = "The request conflicts with the current state of the resource."


def _code_for(exc):
    codes = exc.get_codes()
    if isinstance(codes, str):
        return codes
    return exc.default_code


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)

    if response is None:
        logger.exception("Unhandled error in %s", context.get("view"), exc_info=exc)
        return Response(
            error_body("api_error", "internal_error", "An unexpected error occurred."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    error_type = getattr(exc, "error_type", None) or ERROR_TYPES.get(
        response.status_code, "api_error"
    )

    if isinstance(exc, exceptions.ValidationError):
        detail = exc.detail
        if isinstance(detail, list):
            detail = {"non_field_errors": detail}
        body = error_body(
            error_type, "validation_error", "Invalid request parameters.", fields=detail
        )
    else:
        body = error_body(error_type, _code_for(exc), str(exc.detail))
        if isinstance(exc, exceptions.Throttled) and exc.wait is not None:
            body["error"]["retry_after"] = int(exc.wait)

    response.data = body
    return response
