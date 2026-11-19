import re
import uuid

REQUEST_ID_HEADER = "X-Request-Id"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIdMiddleware:
    """Propagates X-Request-Id (or generates one) so a request can be traced in logs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request.request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        response = self.get_response(request)
        response[REQUEST_ID_HEADER] = request.request_id
        return response
