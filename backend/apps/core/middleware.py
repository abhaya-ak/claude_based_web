import logging
import re
import time
import uuid

from apps.core.logging import get_correlation_id, set_correlation_id

REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
access_logger = logging.getLogger("apps.core.access")


class CorrelationIdMiddleware:
    """Extracts, validates, or generates a request correlation ID for tracing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming_id = request.headers.get("x-request-id") or request.META.get("HTTP_X_REQUEST_ID", "")
        if incoming_id and REQUEST_ID_REGEX.match(incoming_id):
            req_id = incoming_id
        else:
            req_id = uuid.uuid4().hex

        request.correlation_id = req_id
        request.id = req_id
        set_correlation_id(req_id)

        try:
            response = self.get_response(request)
        finally:
            set_correlation_id("")

        response["X-Request-ID"] = req_id
        return response


class AccessLogMiddleware:
    """Emits a single-line structured access log at INFO level with no PII or query strings."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        req_id = getattr(request, "correlation_id", "") or get_correlation_id()

        access_logger.info(
            "%s %s %s %sms",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
