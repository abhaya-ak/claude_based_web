import logging
import re
import time
import uuid

from django.conf import settings
from django.db import connection
from django.http import JsonResponse

from apps.core.logging import get_correlation_id, set_correlation_id

REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
access_logger = logging.getLogger("apps.core.access")


class HealthCheckMiddleware:
    """Answers /api/v1/health/ and /api/v1/health/ready/ directly before host validation (R-D4 / D29)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if path in ("/api/v1/health/", "/health/"):
            return JsonResponse({"status": "ok"}, status=200)
        if path in ("/api/v1/health/ready/", "/health/ready/"):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                return JsonResponse({"status": "ready", "database": "ok"}, status=200)
            except Exception:
                return JsonResponse({"status": "unavailable", "database": "error"}, status=503)

        return self.get_response(request)


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


class RequestSizeLimitMiddleware:
    """Rejects Content-Length above 16 MB before parsing with 413 and code payload_too_large per D71."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                cl_int = int(content_length)
                max_bytes = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 16 * 1024 * 1024)
                if cl_int > max_bytes:
                    req_id = getattr(request, "correlation_id", "") or get_correlation_id()
                    resp = JsonResponse(
                        {
                            "error": {
                                "code": "payload_too_large",
                                "message": f"Request payload exceeds the maximum allowed size of {max_bytes} bytes.",
                                "details": None,
                                "request_id": req_id,
                            }
                        },
                        status=413,
                    )
                    if req_id:
                        resp["X-Request-ID"] = req_id
                    return resp
            except (ValueError, TypeError):
                pass
        return self.get_response(request)


class AccessLogMiddleware:
    """Emits a single-line structured access log at INFO level with no PII or query strings."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        req_id = getattr(request, "correlation_id", "") or get_correlation_id()
        user = getattr(request, "user", None)
        user_id = str(user.id) if (user and getattr(user, "is_authenticated", False)) else None

        access_logger.info(
            "%s %s %s %sms",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": req_id,
                "user_id": user_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
