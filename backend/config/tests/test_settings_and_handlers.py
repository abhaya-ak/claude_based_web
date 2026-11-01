import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client, RequestFactory

BASE_DIR = Path(__file__).resolve().parent.parent.parent

VALID_PROD_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings.prod",
    "DJANGO_SECRET_KEY": "a-very-long-production-secret-key-that-exceeds-fifty-characters-secure",
    "JWT_SIGNING_KEY": "a-secure-jwt-signing-key-32-chars-long",
    "HMAC_IP_SALT": "a-secure-hmac-ip-salt-32-characters-long",
    "INDICATOR_HMAC_KEY": "a-secure-indicator-key-32-chars-long",
    "ALLOWED_HOSTS": "api.scamshield.example.com",
    "PUBLIC_BASE_URL": "https://api.scamshield.example.com",
    "TRUSTED_PROXY_HOPS": "2",
    "DB_NAME": "scamshield_prod",
    "DB_USER": "scamshield_prod_user",
    "DB_PASSWORD": "supersecretpassword",
    "DB_HOST": "rds.example.internal",
    "DB_PORT": "5432",
    "DB_SSLMODE": "require",
    "AWS_DEFAULT_REGION": "ap-southeast-1",
    "AWS_REGION": "ap-southeast-1",
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_EC2_METADATA_DISABLED": "true",
}


def run_prod_subprocess(code: str, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
    """Run Python snippet in isolated environment configured with prod settings."""
    env = os.environ.copy()
    env.update(VALID_PROD_ENV)
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        env=env,
    )


class TestProdSettingsFailFast:
    """Verify that config.settings.prod fails fast on missing or invalid configuration."""

    BOOT_CODE = (
        "import django; "
        "from django.conf import settings; "
        "django.setup(); "
        "print('BOOT_OK', settings.DEBUG, settings.DATABASES['default']['OPTIONS'])"
    )

    def test_prod_boots_with_valid_env(self):
        res = run_prod_subprocess(self.BOOT_CODE)
        assert res.returncode == 0, f"Prod failed to boot with valid env: {res.stderr}"
        assert "BOOT_OK False" in res.stdout
        assert "require" in res.stdout

    def test_prod_fails_when_debug_is_true(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"DEBUG": "True"})
        assert res.returncode != 0
        assert "ImproperlyConfigured" in res.stderr or "DEBUG" in res.stderr

    def test_prod_fails_missing_secret_key(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"DJANGO_SECRET_KEY": None})
        assert res.returncode != 0
        assert "DJANGO_SECRET_KEY" in res.stderr

    def test_prod_fails_short_secret_key(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"DJANGO_SECRET_KEY": "too-short-secret-key"})
        assert res.returncode != 0
        assert "50" in res.stderr or "DJANGO_SECRET_KEY" in res.stderr

    def test_prod_fails_insecure_prefix_secret_key(self):
        insecure_key = "django-insecure-" + ("a" * 40)
        res = run_prod_subprocess(self.BOOT_CODE, {"DJANGO_SECRET_KEY": insecure_key})
        assert res.returncode != 0
        assert "django-insecure" in res.stderr

    def test_prod_fails_missing_jwt_signing_key(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"JWT_SIGNING_KEY": None})
        assert res.returncode != 0
        assert "JWT_SIGNING_KEY" in res.stderr

    def test_prod_fails_short_jwt_signing_key(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"JWT_SIGNING_KEY": "short-key"})
        assert res.returncode != 0
        assert "32" in res.stderr or "JWT_SIGNING_KEY" in res.stderr

    def test_prod_fails_missing_hmac_ip_salt(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"HMAC_IP_SALT": None})
        assert res.returncode != 0
        assert "HMAC_IP_SALT" in res.stderr

    def test_prod_fails_short_hmac_ip_salt(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"HMAC_IP_SALT": "short-salt"})
        assert res.returncode != 0
        assert "32" in res.stderr or "HMAC_IP_SALT" in res.stderr

    def test_prod_fails_missing_indicator_hmac_key(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"INDICATOR_HMAC_KEY": None})
        assert res.returncode != 0
        assert "INDICATOR_HMAC_KEY" in res.stderr

    def test_prod_fails_short_indicator_hmac_key(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"INDICATOR_HMAC_KEY": "short-key"})
        assert res.returncode != 0
        assert "32" in res.stderr or "INDICATOR_HMAC_KEY" in res.stderr

    def test_prod_fails_missing_allowed_hosts(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"ALLOWED_HOSTS": ""})
        assert res.returncode != 0
        assert "ALLOWED_HOSTS" in res.stderr

    def test_prod_fails_missing_public_base_url(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"PUBLIC_BASE_URL": ""})
        assert res.returncode != 0
        assert "PUBLIC_BASE_URL" in res.stderr

    def test_prod_fails_missing_trusted_proxy_hops(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"TRUSTED_PROXY_HOPS": None})
        assert res.returncode != 0
        assert "TRUSTED_PROXY_HOPS" in res.stderr

    def test_prod_fails_negative_trusted_proxy_hops(self):
        res = run_prod_subprocess(self.BOOT_CODE, {"TRUSTED_PROXY_HOPS": "-1"})
        assert res.returncode != 0
        assert "TRUSTED_PROXY_HOPS" in res.stderr

    @pytest.mark.parametrize("db_var", ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"])
    def test_prod_fails_missing_db_credentials(self, db_var):
        res = run_prod_subprocess(self.BOOT_CODE, {db_var: None})
        assert res.returncode != 0
        assert db_var in res.stderr

    def test_prod_check_deploy_passes_cleanly(self):
        """DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy passes with --fail-level WARNING."""
        env = os.environ.copy()
        env.update(VALID_PROD_ENV)
        res = subprocess.run(
            [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode == 0, f"check --deploy failed: {res.stderr}\n{res.stdout}"
        # Ensure only W004 and W008 are silenced
        assert "W004" not in res.stderr
        assert "W008" not in res.stderr


class TestBaseAndTestSettings:
    """Verify base and test settings contracts."""

    def test_append_slash_is_false(self):
        assert settings.APPEND_SLASH is False

    def test_root_urlconf_is_config_urls(self):
        assert settings.ROOT_URLCONF == "config.urls"

    def test_drf_json_renderer_only(self):
        renderers = settings.REST_FRAMEWORK.get("DEFAULT_RENDERER_CLASSES", [])
        assert renderers == ["rest_framework.renderers.JSONRenderer"]

    def test_drf_authenticated_by_default(self):
        permissions = settings.REST_FRAMEWORK.get("DEFAULT_PERMISSION_CLASSES", [])
        assert permissions == ["rest_framework.permissions.IsAuthenticated"]

    def test_drf_unauthenticated_user_is_none(self):
        assert settings.REST_FRAMEWORK.get("UNAUTHENTICATED_USER") is None

    def test_database_options_and_connection_age(self):
        db_conf = settings.DATABASES["default"]
        assert db_conf.get("CONN_MAX_AGE") == 60
        assert db_conf.get("ATOMIC_REQUESTS") is False
        options = db_conf.get("OPTIONS", {})
        assert "-c statement_timeout=10000" in options.get("options", "")

    def test_timezone_and_utc(self):
        assert settings.USE_TZ is True
        assert settings.TIME_ZONE == "UTC"


class TestRootJsonErrorHandlers:
    """Verify root error handlers 400, 403, 404, 500 conform to D26 error envelope."""

    def test_handler400_structure(self, rf: RequestFactory):
        from config.urls import bad_request_handler

        request = rf.get("/bad-req")
        response = bad_request_handler(request)
        assert response.status_code == 400
        assert response["content-type"] == "application/json"
        body = json.loads(response.content)
        assert body == {
            "error": {
                "code": "BAD_REQUEST",
                "message": "Bad request.",
                "details": None,
                "request_id": "",
            }
        }

    def test_handler403_structure(self, rf: RequestFactory):
        from config.urls import permission_denied_handler

        request = rf.get("/forbidden")
        response = permission_denied_handler(request)
        assert response.status_code == 403
        assert response["content-type"] == "application/json"
        body = json.loads(response.content)
        assert body == {
            "error": {
                "code": "PERMISSION_DENIED",
                "message": "Permission denied.",
                "details": None,
                "request_id": "",
            }
        }

    def test_handler404_structure(self, rf: RequestFactory):
        from config.urls import not_found_handler

        request = rf.get("/not-found")
        response = not_found_handler(request)
        assert response.status_code == 404
        assert response["content-type"] == "application/json"
        body = json.loads(response.content)
        assert body == {
            "error": {
                "code": "NOT_FOUND",
                "message": "Not found.",
                "details": None,
                "request_id": "",
            }
        }

    def test_handler500_structure(self, rf: RequestFactory):
        from config.urls import server_error_handler

        request = rf.get("/server-error")
        response = server_error_handler(request)
        assert response.status_code == 500
        assert response["content-type"] == "application/json"
        body = json.loads(response.content)
        assert body == {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "details": None,
                "request_id": "",
            }
        }

    def test_handlers_propagate_request_id(self, rf: RequestFactory):
        from config.urls import not_found_handler

        request = rf.get("/not-found", HTTP_X_REQUEST_ID="test-request-id-1234")
        response = not_found_handler(request)
        body = json.loads(response.content)
        assert body["error"]["request_id"] == "test-request-id-1234"

    def test_not_found_client_integration(self):
        client = Client()
        response = client.get("/nonexistent-endpoint-404-test/")
        assert response.status_code == 404
        assert response["content-type"] == "application/json"
        body = response.json()
        assert body["error"]["code"] == "NOT_FOUND"


class TestAwsTestSafetyFixture:
    """Verify conftest autouse fixture blocks accidental AWS access."""

    def test_aws_env_is_blocked(self):
        assert os.environ.get("AWS_ACCESS_KEY_ID") == "testing"
        assert os.environ.get("AWS_SECRET_ACCESS_KEY") == "testing"
        assert os.environ.get("AWS_DEFAULT_REGION") == "ap-southeast-1"
        assert os.environ.get("AWS_EC2_METADATA_DISABLED") == "true"
