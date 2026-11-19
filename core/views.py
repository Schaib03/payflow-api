from django.db import connection
from django.http import JsonResponse

from core.exceptions import error_body


def liveness(request):
    """The process is up. Does not touch dependencies on purpose."""
    return JsonResponse({"status": "ok"})


def health(request):
    """Readiness: the app can serve traffic, which means the database answers."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable", "database": "down"}, status=503)
    return JsonResponse({"status": "ok", "database": "up"})


def not_found(request, exception=None):
    return JsonResponse(
        error_body("not_found_error", "not_found", "The requested resource does not exist."),
        status=404,
    )


def server_error(request):
    return JsonResponse(
        error_body("api_error", "internal_error", "An unexpected error occurred."), status=500
    )
