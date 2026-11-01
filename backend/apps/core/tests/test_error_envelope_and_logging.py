import json
import logging
import uuid

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.request import Request

from apps.core.exceptions import PayloadTooLarge, custom_exception_handler
from apps.core.logging import FORBIDDEN_PII_KEYS, PiiScrubberFilter, get_correlation_id
from apps.core.middleware import AccessLogMiddleware, CorrelationIdMiddleware, RequestSizeLimitMiddleware
from apps.core.pagination import StandardPagination


class TestCorrelationIdMiddleware:
    """Verify request ID extraction, validation, fallback, and ContextVar propagation."""

    def test_valid_incoming_x_request_id_preserved(self, rf: RequestFactory):
        valid_id = "req-12345678-abc"
        request = rf.get("/test", HTTP_X_REQUEST_ID=valid_id)
        middleware = CorrelationIdMiddleware(lambda r: HttpResponse("OK"))

        response = middleware(request)
        assert response["X-Request-ID"] == valid_id
        assert request.correlation_id == valid_id
        # ContextVar is cleaned up after request
        assert get_correlation_id() == ""

    def test_missing_x_request_id_generates_uuid4_hex(self, rf: RequestFactory):
        request = rf.get("/test")
        middleware = CorrelationIdMiddleware(lambda r: HttpResponse("OK"))

        response = middleware(request)
        generated_id = response["X-Request-ID"]
        assert len(generated_id) == 32
        # Verify valid hex
        assert uuid.UUID(hex=generated_id)
        assert request.correlation_id == generated_id

    @pytest.mark.parametrize(
        "invalid_id",
        [
            "short",  # < 8 chars
            "a" * 65,  # > 64 chars
            "invalid id with spaces",
            "<script>alert(1)</script>",
            "id@with!symbols$",
        ],
    )
    def test_invalid_x_request_id_replaced_with_uuid4_hex(self, rf: RequestFactory, invalid_id: str):
        request = rf.get("/test", HTTP_X_REQUEST_ID=invalid_id)
        middleware = CorrelationIdMiddleware(lambda r: HttpResponse("OK"))

        response = middleware(request)
        generated_id = response["X-Request-ID"]
        assert generated_id != invalid_id
        assert len(generated_id) == 32
        assert uuid.UUID(hex=generated_id)

    def test_contextvar_accessible_during_request(self, rf: RequestFactory):
        captured_id = None

        def view(request):
            nonlocal captured_id
            captured_id = get_correlation_id()
            return HttpResponse("OK")

        request = rf.get("/test", HTTP_X_REQUEST_ID="correlation-id-999")
        middleware = CorrelationIdMiddleware(view)
        middleware(request)

        assert captured_id == "correlation-id-999"
        # Reset after request completes
        assert get_correlation_id() == ""


class TestDrfCustomExceptionHandler:
    """Verify DRF custom exception handler conforms to D26 envelope."""

    def test_validation_error_envelope(self, rf: RequestFactory):
        request = Request(rf.post("/api/test", HTTP_X_REQUEST_ID="req-val-123"))
        request.correlation_id = "req-val-123"
        exc = drf_exceptions.ValidationError({"email": ["Invalid email format."]})

        response = custom_exception_handler(exc, {"request": request})
        assert response is not None
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["message"] == "Validation failed."
        assert data["error"]["details"] == {"email": ["Invalid email format."]}
        assert data["error"]["request_id"] == "req-val-123"

    def test_not_authenticated_envelope(self, rf: RequestFactory):
        request = Request(rf.get("/api/test"))
        request.correlation_id = "req-auth-401"
        exc = drf_exceptions.NotAuthenticated("Authentication credentials were not provided.")

        response = custom_exception_handler(exc, {"request": request})
        assert response is not None
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.data
        assert data["error"]["code"] == "NOT_AUTHENTICATED"
        assert data["error"]["details"] is None
        assert data["error"]["request_id"] == "req-auth-401"

    def test_permission_denied_envelope(self, rf: RequestFactory):
        request = Request(rf.get("/api/test"))
        request.correlation_id = "req-perm-403"
        exc = drf_exceptions.PermissionDenied("You do not have permission.")

        response = custom_exception_handler(exc, {"request": request})
        assert response is not None
        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.data
        assert data["error"]["code"] == "PERMISSION_DENIED"
        assert data["error"]["details"] is None
        assert data["error"]["request_id"] == "req-perm-403"

    def test_not_found_envelope(self, rf: RequestFactory):
        request = Request(rf.get("/api/test"))
        request.correlation_id = "req-nf-404"
        exc = drf_exceptions.NotFound("Resource not found.")

        response = custom_exception_handler(exc, {"request": request})
        assert response is not None
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.data
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["details"] is None
        assert data["error"]["request_id"] == "req-nf-404"

    def test_method_not_allowed_envelope(self, rf: RequestFactory):
        request = Request(rf.get("/api/test"))
        request.correlation_id = "req-mna-405"
        exc = drf_exceptions.MethodNotAllowed("GET")

        response = custom_exception_handler(exc, {"request": request})
        assert response is not None
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        data = response.data
        assert data["error"]["code"] == "METHOD_NOT_ALLOWED"
        assert data["error"]["details"] is None
        assert data["error"]["request_id"] == "req-mna-405"

    def test_throttled_envelope_with_retry_after(self, rf: RequestFactory):
        request = Request(rf.get("/api/test"))
        request.correlation_id = "req-throttle-429"
        exc = drf_exceptions.Throttled(wait=60)

        response = custom_exception_handler(exc, {"request": request})
        assert response is not None
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.get("Retry-After") == "60"
        data = response.data
        assert data["error"]["code"] == "RATE_LIMITED"
        assert data["error"]["details"] is None
        assert data["error"]["request_id"] == "req-throttle-429"

    def test_payload_too_large_envelope(self, rf: RequestFactory):
        request = Request(rf.post("/api/test"))
        request.correlation_id = "req-413-large"
        exc = PayloadTooLarge("Payload exceeds limit.")

        response = custom_exception_handler(exc, {"request": request})
        assert response is not None
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        data = response.data
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert data["error"]["message"] == "Payload exceeds limit."
        assert data["error"]["request_id"] == "req-413-large"

    def test_unhandled_500_exception_never_leaks_details(self, rf: RequestFactory):
        request = Request(rf.get("/api/test"))
        request.correlation_id = "req-crash-500"
        exc = RuntimeError("Database connection string postgres://secret_pw@host failed")

        response = custom_exception_handler(exc, {"request": request})
        assert response is not None
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.data
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert data["error"]["message"] == "An internal server error occurred."
        assert data["error"]["details"] is None
        assert data["error"]["request_id"] == "req-crash-500"
        # Verify secret/internal info is NOT in response body
        assert "secret_pw" not in json.dumps(data)
        assert "RuntimeError" not in json.dumps(data)


class TestStandardPagination:
    """Verify limit/offset StandardPagination contract."""

    def test_pagination_defaults_and_max(self):
        pagination = StandardPagination()
        assert pagination.default_limit == 20
        assert pagination.max_limit == 100

    def test_pagination_response_envelope(self, rf: RequestFactory):
        pagination = StandardPagination()
        queryset = list(range(50))
        request = Request(rf.get("/items?limit=10&offset=20"))

        page = pagination.paginate_queryset(queryset, request)
        response = pagination.get_paginated_response(page)
        data = response.data

        assert set(data.keys()) == {"count", "next", "previous", "results"}
        assert data["count"] == 50
        assert len(data["results"]) == 10
        assert data["results"] == list(range(20, 30))
        assert "limit=10" in data["next"]
        assert "offset=30" in data["next"]
        assert "limit=10" in data["previous"]


class TestPiiScrubberFilter:
    """Verify PII scrubber masks the 16 forbidden keys."""

    def test_forbidden_keys_exact_set(self):
        expected_16 = {
            "password",
            "token",
            "secret",
            "authorization",
            "cookie",
            "phone",
            "email",
            "bank_account",
            "id_number",
            "victim_name",
            "reporter_name",
            "evidence",
            "national_id",
            "credit_card",
            "pin",
            "cvv",
        }
        assert FORBIDDEN_PII_KEYS == expected_16

    @pytest.mark.parametrize("key", sorted(FORBIDDEN_PII_KEYS))
    def test_scrubber_masks_dict_keys(self, key: str):
        scrubber = PiiScrubberFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User action performed",
            args=(),
            exc_info=None,
        )
        record.sensitive_data = {key: "raw_secret_value", "safe_field": "public_val"}
        scrubber.filter(record)

        assert record.sensitive_data[key] == "[REDACTED]"
        assert record.sensitive_data["safe_field"] == "public_val"

    def test_scrubber_removes_raw_request_object(self, rf: RequestFactory):
        scrubber = PiiScrubberFilter()
        request = rf.get("/api/v1/test/?sensitive_param=leak123")
        record = logging.LogRecord(
            name="django.request",
            level=logging.WARNING,
            pathname="handler.py",
            lineno=10,
            msg="Not Found",
            args=(),
            exc_info=None,
        )
        record.request = request
        scrubber.filter(record)
        assert not hasattr(record, "request")


class TestAccessLogMiddleware:
    """Verify single-line access log contains required fields without query strings or headers."""

    def test_access_log_emits_structured_info(self, rf: RequestFactory, caplog: pytest.LogCaptureFixture):
        request = rf.get("/api/v1/reports/?query=secret_leak", HTTP_AUTHORIZATION="Bearer token123")
        request.correlation_id = "req-access-001"

        def view(req):
            return HttpResponse("OK", status=200)

        middleware = AccessLogMiddleware(view)
        with caplog.at_level(logging.INFO, logger="apps.core.access"):
            middleware(request)

        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert record.levelno == logging.INFO
        assert getattr(record, "request_id", "") == "req-access-001"
        assert getattr(record, "method", "") == "GET"
        assert getattr(record, "status_code", 0) == 200
        assert getattr(record, "path", "") == "/api/v1/reports/"
        assert hasattr(record, "duration_ms")
        # Ensure query string was NOT logged in path or message
        assert "secret_leak" not in record.getMessage()
        assert "secret_leak" not in str(getattr(record, "path", ""))
        # Ensure authorization header is NOT logged
        assert "token123" not in record.getMessage()
        # Ensure user_id is present and null for unauthenticated request
        assert hasattr(record, "user_id")
        assert getattr(record, "user_id", None) is None



    def test_access_log_includes_user_id_for_authenticated_user(
        self, rf: RequestFactory, caplog: pytest.LogCaptureFixture
    ):
        import uuid
        from unittest.mock import MagicMock

        request = rf.get("/api/v1/reports/")
        request.correlation_id = "req-access-002"
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.id = uuid.uuid4()
        request.user = mock_user

        def view(req):
            return HttpResponse("OK", status=200)

        middleware = AccessLogMiddleware(view)
        with caplog.at_level(logging.INFO, logger="apps.core.access"):
            middleware(request)

        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert getattr(record, "user_id", None) == str(mock_user.id)

    def test_access_log_user_id_null_for_anonymous_user(
        self, rf: RequestFactory, caplog: pytest.LogCaptureFixture
    ):
        from django.contrib.auth.models import AnonymousUser

        request = rf.get("/api/v1/reports/")
        request.correlation_id = "req-access-003"
        request.user = AnonymousUser()

        def view(req):
            return HttpResponse("OK", status=200)

        middleware = AccessLogMiddleware(view)
        with caplog.at_level(logging.INFO, logger="apps.core.access"):
            middleware(request)

        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "user_id")
        assert getattr(record, "user_id", None) is None


class TestRequestSizeLimitMiddleware:
    """Verify Content-Length exceeding 16 MB is rejected with 413 per D71."""

    def test_oversized_content_length_rejected_with_413(self, rf: RequestFactory):
        oversized = str(16 * 1024 * 1024 + 1)
        request = rf.post("/api/v1/reports/", CONTENT_LENGTH=oversized)
        request.correlation_id = "req-large-413"

        middleware = RequestSizeLimitMiddleware(lambda r: HttpResponse("OK"))
        response = middleware(request)

        assert response.status_code == 413
        assert response["X-Request-ID"] == "req-large-413"
        data = json.loads(response.content)
        assert data["error"]["code"] == "payload_too_large"
        assert data["error"]["request_id"] == "req-large-413"

    def test_acceptable_content_length_allowed(self, rf: RequestFactory):
        normal_size = str(5 * 1024 * 1024)
        request = rf.post("/api/v1/reports/", CONTENT_LENGTH=normal_size)
        request.correlation_id = "req-normal-200"

        middleware = RequestSizeLimitMiddleware(lambda r: HttpResponse("OK"))
        response = middleware(request)

        assert response.status_code == 200
