import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.core.logging import get_correlation_id

logger = logging.getLogger(__name__)


def _extract_request_id(request) -> str:
    if request:
        req_id = getattr(request, "correlation_id", None) or getattr(request, "id", None)
        if req_id:
            return str(req_id)
        if hasattr(request, "headers"):
            hdr = request.headers.get("x-request-id")
            if hdr:
                return hdr
        if hasattr(request, "META"):
            hdr = request.META.get("HTTP_X_REQUEST_ID")
            if hdr:
                return hdr
    return get_correlation_id()


def custom_exception_handler(exc, context):
    """DRF custom exception handler returning the standardized D26 error envelope."""
    request = context.get("request")
    request_id = _extract_request_id(request)

    # Let DRF handle standard exceptions first
    response = exception_handler(exc, context)

    if response is not None:
        status_code = response.status_code
        details = None
        message = "An error occurred."
        code = "API_ERROR"

        if isinstance(exc, drf_exceptions.ValidationError):
            code = "VALIDATION_ERROR"
            message = "Validation failed."
            details = response.data
        elif isinstance(exc, (drf_exceptions.NotAuthenticated, drf_exceptions.AuthenticationFailed)):
            code = "NOT_AUTHENTICATED"
            detail = response.data.get("detail", "Authentication credentials were not provided.")
            message = str(detail)
        elif isinstance(exc, (drf_exceptions.PermissionDenied, DjangoPermissionDenied)):
            code = "PERMISSION_DENIED"
            detail = response.data.get("detail", "You do not have permission to perform this action.")
            message = str(detail)
        elif isinstance(exc, (drf_exceptions.NotFound, Http404)):
            code = "NOT_FOUND"
            detail = response.data.get("detail", "Not found.")
            message = str(detail)
        elif isinstance(exc, drf_exceptions.MethodNotAllowed):
            code = "METHOD_NOT_ALLOWED"
            detail = response.data.get("detail", "Method not allowed.")
            message = str(detail)
        elif isinstance(exc, drf_exceptions.Throttled):
            code = "RATE_LIMITED"
            detail = response.data.get("detail", "Request was throttled.")
            message = str(detail)
            if exc.wait is not None:
                response["Retry-After"] = str(int(exc.wait))
        elif status_code == status.HTTP_409_CONFLICT:
            code = "CONFLICT"
            detail = response.data.get("detail", "A conflict occurred.")
            message = str(detail)
        else:
            if isinstance(response.data, dict) and "detail" in response.data:
                message = str(response.data["detail"])
            code = f"HTTP_{status_code}"

        response.data = {
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id,
            }
        }
        return response

    # Unhandled 500 error
    logger.exception("Unhandled server error processing request: %s", exc)
    return Response(
        {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "details": None,
                "request_id": request_id,
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
