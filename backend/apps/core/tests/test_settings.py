import pytest
from django.core.exceptions import ImproperlyConfigured


def test_prod_settings_fail_fast_on_insecure_refresh_cookie(monkeypatch):
    """D43: In config/settings/prod.py, REFRESH_COOKIE_SECURE must be True or fail fast."""
    monkeypatch.setenv("REFRESH_COOKIE_SECURE", "False")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "prod-secret-key-12345678901234567890")
    monkeypatch.setenv("JWT_SIGNING_KEY", "prod-jwt-key-12345678901234567890")
    monkeypatch.setenv("ALLOWED_HOSTS", "scamshield.example.com")
    monkeypatch.setenv("DEBUG", "False")

    with pytest.raises(ImproperlyConfigured) as exc:
        import importlib
        import sys

        if "config.settings.prod" in sys.modules:
            del sys.modules["config.settings.prod"]
        importlib.import_module("config.settings.prod")

    assert "REFRESH_COOKIE_SECURE" in str(exc.value)
