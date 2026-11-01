import logging
import uuid

from rest_framework import exceptions, status
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class AccountNotApproved(exceptions.APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Account is pending administrator approval."
    default_code = "account_not_approved"


class ConflictError(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict occurred."
    default_code = "conflict"


def custom_exception_handler(exc, context):
    """
    Standard DRF exception handler implementing the ScamShield error envelope:
    {"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}
    """
    from rest_framework.views import exception_handler

    request = context.get("request") if context else None
    request_id = None
    if request:
        request_id = getattr(request, "request_id", None) or request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())

    response = exception_handler(exc, context)

    if response is None:
        logger.exception("Unhandled server exception: %s", exc)
        payload = {
            "error": {
                "code": "server_error",
                "message": "An internal server error occurred.",
                "details": {},
                "request_id": request_id,
            }
        }
        response = Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        response.headers["X-Request-ID"] = request_id
        return response

    # Determine code and message
    code = getattr(exc, "default_code", None)
    if isinstance(exc, exceptions.APIException) and hasattr(exc, "get_codes"):
        codes = exc.get_codes()
        if isinstance(codes, str):
            code = codes
        elif isinstance(codes, dict) and "code" in codes:
            code = codes["code"]

    if not code:
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            code = "validation_error"
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            code = "authentication_failed"
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            code = "permission_denied"
        elif response.status_code == status.HTTP_404_NOT_FOUND:
            code = "not_found"
        elif response.status_code == status.HTTP_409_CONFLICT:
            code = "conflict"
        elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            code = "throttled"
        else:
            code = "error"

    # Map message and details
    details = {}
    message = "An error occurred."
    if isinstance(response.data, dict):
        if "detail" in response.data:
            message = str(response.data["detail"])
        else:
            message = "Validation failed."
            details = response.data
    elif isinstance(response.data, list):
        details = {"non_field_errors": response.data}
    elif isinstance(response.data, str):
        message = response.data

    # Throttled header handling
    if isinstance(exc, exceptions.Throttled):
        code = "throttled"
        wait = exc.wait if exc.wait is not None else 900
        response.headers["Retry-After"] = str(int(wait))
        message = f"Request was throttled. Expected available in {int(wait)} seconds."

    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }
    response.data = payload
    response.headers["X-Request-ID"] = request_id
    return response
