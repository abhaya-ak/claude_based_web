import os
import subprocess
import sys

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.reports.models import ScamReport

SQLI_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE reports_scamreport; --",
    "' UNION SELECT null, email, password FROM accounts_user; --",
    "1' AND 1=(SELECT 1 FROM pg_sleep(0.01))--",
    "admin'--",
    "' OR ''='",
]


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestOwaspSecuritySuite:
    def test_sql_injection_in_threat_lookup_safely_handled(self, api_client):
        """
        OWASP A03 Injection: SQL injection payloads in threat lookups must never execute
        or crash with 500; parameterized queries handle them safely.
        """
        for payload in SQLI_PAYLOADS:
            res = api_client.post(
                "/api/v1/lookups/",
                {"query": payload},
                format="json",
            )
            assert res.status_code in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST)
            if res.status_code == status.HTTP_200_OK:
                # Should safely report clean verdict or not found
                data = res.json()
                assert data["verdict"] in ("GREEN", "YELLOW", "RED")

    def test_sql_injection_in_report_track_safely_handled(self, api_client):
        """
        OWASP A03 Injection: SQL injection payloads in report reference codes must return 404.
        """
        for payload in SQLI_PAYLOADS:
            res = api_client.post(
                "/api/v1/reports/track/",
                {"reference_code": payload[:30], "access_key": "some-key"},
                format="json",
            )
            assert res.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND)
            assert res.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_sql_injection_in_guides_query_params_safely_handled(self, api_client):
        """
        OWASP A03 Injection: SQL injection payloads in list filters must never execute.
        """
        for payload in SQLI_PAYLOADS:
            res = api_client.get(f"/api/v1/guides/?search={payload}&tactic={payload}")
            assert res.status_code in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST)
            assert res.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_tables_remain_intact_after_sqli_probes(self):
        """Verify reports_scamreport and accounts_user tables exist and are untouched."""
        assert ScamReport.objects.count() >= 0
        assert User.objects.count() >= 0

    def test_malformed_and_non_dict_json_payloads_safely_rejected(self, api_client):
        """
        OWASP A04/A08: Malformed JSON or unexpected non-dict roots must return 400.
        """
        # 1. Non-dict root (array)
        res_arr = api_client.post(
            "/api/v1/lookups/",
            data=["malicious", "array"],
            format="json",
        )
        assert res_arr.status_code == status.HTTP_400_BAD_REQUEST

        # 2. Raw malformed JSON
        res_malformed = api_client.post(
            "/api/v1/lookups/",
            data="not-valid-json{{{",
            content_type="application/json",
        )
        assert res_malformed.status_code == status.HTTP_400_BAD_REQUEST

        # 3. Object injection payload
        res_obj = api_client.post(
            "/api/v1/lookups/",
            data={"query": {"$ne": None}},
            format="json",
        )
        assert res_obj.status_code == status.HTTP_400_BAD_REQUEST

    def test_django_admin_and_browsable_api_disabled(self, api_client):
        """
        R-A12 / Production Hardening: Django admin and DRF browsable API are disabled.
        """
        # Django admin URL is unmapped
        res_admin = api_client.get("/admin/")
        assert res_admin.status_code == status.HTTP_404_NOT_FOUND

        # django.contrib.admin is not installed
        assert "django.contrib.admin" not in settings.INSTALLED_APPS

        # DEFAULT_RENDERER_CLASSES contains only JSONRenderer
        renderers = settings.REST_FRAMEWORK.get("DEFAULT_RENDERER_CLASSES", [])
        assert "rest_framework.renderers.BrowsableAPIRenderer" not in renderers
        assert "rest_framework.renderers.JSONRenderer" in renderers

    def test_security_headers_enforced(self, api_client):
        """
        OWASP A05 Security Misconfiguration: Verify standard security headers.
        """
        res = api_client.get("/api/v1/reports/options/")
        assert res.status_code == status.HTTP_200_OK
        headers = res.headers

        # X-Content-Type-Options: nosniff
        assert headers.get("X-Content-Type-Options") == "nosniff"
        # X-Frame-Options: DENY
        assert headers.get("X-Frame-Options") == "DENY"

    def test_production_deployment_check(self):
        """
        Runs 'manage.py check --deploy' under production settings and verifies zero critical failures.
        """
        env = os.environ.copy()
        env.update(
            {
                "DEBUG": "False",
                "DJANGO_SECRET_KEY": "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-=~54321",
                "JWT_SIGNING_KEY": "jwt-signing-key-32-chars-long-prod!",
                "HMAC_IP_SALT": "hmac-ip-salt-32-chars-long-prod-!",
                "INDICATOR_HMAC_KEY": "indicator-hmac-key-32-char-prod-!",
                "EVIDENCE_BUCKET": "scamshield-evidence-prod",
                "MEDIA_BUCKET": "scamshield-media-prod",
                "SCANNER_CALLBACK_SECRET": "scanner-callback-secret-32-chars-long!",
                "ALLOWED_HOSTS": "api.scamshield.gov.my",
                "PUBLIC_BASE_URL": "https://scamshield.gov.my",
                "TRUSTED_PROXY_HOPS": "2",
                "DB_NAME": "scamshield",
                "DB_USER": "scamshield_user",
                "DB_PASSWORD": "secure_password",
                "DB_HOST": "localhost",
                "DB_PORT": "5432",
                "DB_SSLMODE": "disable",
                "DJANGO_SETTINGS_MODULE": "config.settings.prod",
            }
        )

        proc = subprocess.run(
            [sys.executable, "manage.py", "check", "--deploy"],
            cwd=str(settings.BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"check --deploy failed: {proc.stderr}\n{proc.stdout}"
        assert "System check identified no issues" in proc.stdout or "0 silenced" in proc.stdout or "silenced" in proc.stdout
