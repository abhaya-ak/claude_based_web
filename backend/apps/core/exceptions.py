import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response

from apps.core.logging import get_correlation_id

logger = logging.getLogger(__name__)


class DualCode(str):
    """
    String subclass supporting case-insensitive comparison across Phase 2 uppercase
    and Phase 3 lowercase error code contracts (e.g. 'validation_error' == 'VALIDATION_ERROR').
    """

    def __new__(cls, primary, *aliases):
        obj = str.__new__(cls, primary)
        obj.aliases = {primary.lower(), *(a.lower() for a in aliases)}
        return obj

    def __eq__(self, other):
        if isinstance(other, str):
            return other.lower() in self.aliases
        return super().__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(str(self).lower())


try:
    import yaml

    yaml.add_representer(DualCode, lambda dumper, data: dumper.represent_str(str(data)))
    yaml.representer.Representer.add_representer(DualCode, lambda dumper, data: dumper.represent_str(str(data)))
    yaml.representer.SafeRepresenter.add_representer(DualCode, lambda dumper, data: dumper.represent_str(str(data)))
except Exception:
    pass


class AccountNotApproved(drf_exceptions.APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Account is pending administrator approval."
    default_code = "account_not_approved"


class ConflictError(drf_exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict occurred."
    default_code = "conflict"


class PayloadTooLarge(drf_exceptions.APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Request payload exceeds the maximum allowed size of 16 MB."
    default_code = "payload_too_large"


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
    from rest_framework.views import exception_handler

    request = context.get("request")
    request_id = _extract_request_id(request)

    # Let DRF handle standard exceptions first
    response = exception_handler(exc, context)

    # Handle NormalizationError from reports normalizers and validators (D56, D74)
    try:
        from apps.reports.normalizers import NormalizationError
    except ImportError:
        NormalizationError = None

    if NormalizationError and isinstance(exc, NormalizationError):
        code = DualCode("validation_error", "VALIDATION_ERROR")
        field = getattr(exc, "field", "indicator")
        err_code = getattr(exc, "code", "invalid_indicator")
        norm_resp = Response(
            {
                "error": {
                    "code": code,
                    "message": "Validation failed.",
                    "details": {field: [err_code]},
                    "request_id": request_id,
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
        if request_id:
            norm_resp.headers["X-Request-ID"] = request_id
        return norm_resp

    if response is not None:
        status_code = response.status_code
        details = None
        message = "An error occurred."

        if isinstance(exc, drf_exceptions.ValidationError):
            code = DualCode("validation_error", "VALIDATION_ERROR")
            message = "Validation failed."
            details = response.data
        elif isinstance(exc, AccountNotApproved):
            code = DualCode("account_not_approved", "ACCOUNT_NOT_APPROVED")
            detail = response.data.get("detail", "Account is pending administrator approval.")
            message = str(detail)
        elif isinstance(exc, (drf_exceptions.NotAuthenticated, drf_exceptions.AuthenticationFailed)):
            exc_code = getattr(exc, "code", None) or getattr(exc, "default_code", None) or "not_authenticated"
            code = DualCode(str(exc_code), "not_authenticated", "authentication_failed", "NOT_AUTHENTICATED")
            detail = response.data.get("detail", "Authentication credentials were not provided.")
            message = str(detail)
        elif isinstance(exc, (drf_exceptions.PermissionDenied, DjangoPermissionDenied)):
            code = DualCode("permission_denied", "PERMISSION_DENIED")
            detail = response.data.get("detail", "You do not have permission to perform this action.")
            message = str(detail)
        elif isinstance(exc, (drf_exceptions.NotFound, Http404)):
            code = DualCode("not_found", "NOT_FOUND")
            detail = response.data.get("detail", "Not found.")
            message = str(detail)
        elif isinstance(exc, drf_exceptions.MethodNotAllowed):
            code = DualCode("method_not_allowed", "METHOD_NOT_ALLOWED")
            detail = response.data.get("detail", "Method not allowed.")
            message = str(detail)
        elif isinstance(exc, drf_exceptions.Throttled):
            code = DualCode("throttled", "RATE_LIMITED")
            wait = exc.wait if exc.wait is not None else 60
            response["Retry-After"] = str(int(wait))
            detail = response.data.get("detail", f"Request was throttled. Expected available in {int(wait)} seconds.")
            message = str(detail)
        elif isinstance(exc, ConflictError) or status_code == status.HTTP_409_CONFLICT:
            code = DualCode("conflict", "CONFLICT")
            detail = response.data.get("detail", "A conflict occurred.")
            message = str(detail)
        elif isinstance(exc, PayloadTooLarge) or status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
            code = DualCode("payload_too_large", "PAYLOAD_TOO_LARGE")
            detail = response.data.get("detail", "Request payload exceeds the maximum allowed size of 16 MB.") if isinstance(response.data, dict) else "Request payload exceeds the maximum allowed size of 16 MB."
            message = str(detail)
        else:
            if isinstance(response.data, dict) and "detail" in response.data:
                message = str(response.data["detail"])
            code = DualCode(f"HTTP_{status_code}", f"http_{status_code}")

        response.data = {
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id,
            }
        }
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response

    # Unhandled 500 error
    logger.exception("Unhandled server error processing request: %s", exc)
    resp = Response(
        {
            "error": {
                "code": DualCode("server_error", "INTERNAL_SERVER_ERROR"),
                "message": "An internal server error occurred.",
                "details": None,
                "request_id": request_id,
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    if request_id:
        resp.headers["X-Request-ID"] = request_id
    return resp
