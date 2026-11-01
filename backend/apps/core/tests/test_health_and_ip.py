import re
from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.core.ip import client_ip_hash, get_client_ip
from apps.core.middleware import HealthCheckMiddleware


class TestHealthCheckEndpoints:
    """Verify health endpoints answer directly and bypass host validation (R-D4 / D29)."""

    def test_liveness_bypasses_allowed_hosts_and_returns_200(self, rf: RequestFactory):
        # Host header is an internal private IP not in ALLOWED_HOSTS
        request = rf.get("/api/v1/health/", HTTP_HOST="10.0.1.50")
        middleware = HealthCheckMiddleware(lambda r: HttpResponse("FALLTHROUGH"))

        response = middleware(request)
        assert response.status_code == 200
        assert response["content-type"] == "application/json"
        assert response.content == b'{"status": "ok"}'

    @pytest.mark.django_db
    def test_readiness_returns_200_when_database_is_healthy(self, rf: RequestFactory):
        request = rf.get("/api/v1/health/ready/", HTTP_HOST="10.0.1.50")
        middleware = HealthCheckMiddleware(lambda r: HttpResponse("FALLTHROUGH"))

        response = middleware(request)
        assert response.status_code == 200
        assert response["content-type"] == "application/json"
        assert b'"status": "ready"' in response.content
        assert b'"database": "ok"' in response.content

    def test_readiness_returns_503_when_database_fails(self, rf: RequestFactory):
        request = rf.get("/api/v1/health/ready/", HTTP_HOST="10.0.1.50")
        middleware = HealthCheckMiddleware(lambda r: HttpResponse("FALLTHROUGH"))

        with patch("django.db.connection.cursor", side_effect=DatabaseError("Connection refused")):
            response = middleware(request)

        assert response.status_code == 503
        assert response["content-type"] == "application/json"
        assert b'"status": "unavailable"' in response.content
        assert b'"database": "error"' in response.content

    def test_non_health_requests_fall_through(self, rf: RequestFactory):
        request = rf.get("/api/v1/other/")
        middleware = HealthCheckMiddleware(lambda r: HttpResponse("PASS_TO_NEXT", status=200))

        response = middleware(request)
        assert response.status_code == 200
        assert response.content == b"PASS_TO_NEXT"


class TestClientIpAndHashing:
    """Verify client IP extraction with TRUSTED_PROXY_HOPS and HMAC-SHA256 hashing (R-C7 / D30)."""

    @override_settings(TRUSTED_PROXY_HOPS=0)
    def test_get_client_ip_zero_hops_uses_remote_addr(self, rf: RequestFactory):
        request = rf.get("/test", REMOTE_ADDR="192.168.1.100", HTTP_X_FORWARDED_FOR="10.0.0.1")
        ip = get_client_ip(request)
        assert ip == "192.168.1.100"

    @override_settings(TRUSTED_PROXY_HOPS=1)
    def test_get_client_ip_one_hop_alb(self, rf: RequestFactory):
        request = rf.get(
            "/test",
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="203.0.113.195, 10.0.0.1",
        )
        ip = get_client_ip(request)
        assert ip == "203.0.113.195"

    @override_settings(TRUSTED_PROXY_HOPS=2)
    def test_get_client_ip_two_hops_cloudfront_plus_alb(self, rf: RequestFactory):
        # Client -> CloudFront -> ALB -> EC2
        request = rf.get(
            "/test",
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="198.51.100.25, 130.176.0.1, 10.0.0.1",
        )
        ip = get_client_ip(request)
        assert ip == "198.51.100.25"

    @override_settings(TRUSTED_PROXY_HOPS=2)
    def test_get_client_ip_fewer_hops_than_configured_falls_back(self, rf: RequestFactory):
        request = rf.get(
            "/test",
            REMOTE_ADDR="192.168.1.5",
            HTTP_X_FORWARDED_FOR="203.0.113.10",
        )
        ip = get_client_ip(request)
        # Safe fallback
        assert ip in ("203.0.113.10", "192.168.1.5")

    @override_settings(TRUSTED_PROXY_HOPS=1)
    def test_get_client_ip_handles_ipv6(self, rf: RequestFactory):
        request = rf.get(
            "/test",
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="2001:db8:85a3::8a2e:370:7334, 10.0.0.1",
        )
        ip = get_client_ip(request)
        assert ip == "2001:db8:85a3::8a2e:370:7334"

    @override_settings(TRUSTED_PROXY_HOPS=1)
    def test_get_client_ip_invalid_ip_falls_back(self, rf: RequestFactory):
        request = rf.get(
            "/test",
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_FORWARDED_FOR="not-an-ip, 10.0.0.1",
        )
        ip = get_client_ip(request)
        assert ip == "127.0.0.1"

    @override_settings(TRUSTED_PROXY_HOPS=0, HMAC_IP_SALT="test-hmac-salt-at-least-32-chars!")
    def test_client_ip_hash_returns_64_hex_chars(self, rf: RequestFactory):
        request = rf.get("/test", REMOTE_ADDR="198.51.100.55")
        ip_hash = client_ip_hash(request)

        assert len(ip_hash) == 64
        assert re.match(r"^[0-9a-f]{64}$", ip_hash)

    @override_settings(TRUSTED_PROXY_HOPS=0, HMAC_IP_SALT="test-hmac-salt-at-least-32-chars!")
    def test_client_ip_hash_deterministic_and_unique(self, rf: RequestFactory):
        req1 = rf.get("/test", REMOTE_ADDR="198.51.100.55")
        req2 = rf.get("/test", REMOTE_ADDR="198.51.100.55")
        req3 = rf.get("/test", REMOTE_ADDR="203.0.113.88")

        assert client_ip_hash(req1) == client_ip_hash(req2)
        assert client_ip_hash(req1) != client_ip_hash(req3)
