import hashlib
import hmac
import time

from django.conf import settings
from rest_framework import exceptions
from rest_framework.permissions import BasePermission


class HasValidScannerSignature(BasePermission):
    """
    Validates machine-to-machine HMAC-SHA256 signature and timestamp for scanner callbacks (D90).
    Ensures:
    1. Headers X-Timestamp and X-Signature are present.
    2. X-Timestamp is a valid integer.
    3. Timestamp is within +/- 300 seconds (5 minutes) clock skew window.
    4. Signature matches HMAC-SHA256 over f"{timestamp}." + request.body using internal callback key.
    """

    message = "Invalid or missing scanner signature."
    code = "permission_denied"

    def has_permission(self, request, view):
        # 1. Extract headers (check both request.headers and request.META)
        timestamp_str = (
            (request.headers.get("X-Timestamp") if hasattr(request, "headers") else None)
            or request.META.get("HTTP_X_TIMESTAMP")
        )
        provided_sig = (
            (request.headers.get("X-Signature") if hasattr(request, "headers") else None)
            or request.META.get("HTTP_X_SIGNATURE")
        )

        if not timestamp_str or not provided_sig:
            raise exceptions.PermissionDenied("Missing scanner signature or timestamp.")

        # 2. Non-integer X-Timestamp -> 403 permission_denied
        try:
            timestamp_int = int(timestamp_str)
        except (ValueError, TypeError) as err:
            raise exceptions.PermissionDenied("Invalid scanner timestamp.") from err

        # 3. Enforce clock skew window: abs(current_time - timestamp_int) <= 300
        now = int(time.time())
        if abs(now - timestamp_int) > 300:
            raise exceptions.PermissionDenied("Scanner signature timestamp outside allowed clock skew window.")

        # 4. Callback secret key
        secret = (
            getattr(settings, "INTERNAL_CALLBACK_HMAC_KEY", None)
            or getattr(settings, "SCANNER_CALLBACK_SECRET", None)
            or ""
        )
        if not secret:
            raise exceptions.PermissionDenied("Internal callback HMAC key is not configured.")

        # 5. Compute expected HMAC-SHA256 hex digest over raw request body
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp_str}.".encode() + request.body,
            hashlib.sha256,
        ).hexdigest()

        # 6. Constant-time comparison
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise exceptions.PermissionDenied("Scanner signature mismatch.")

        return True
