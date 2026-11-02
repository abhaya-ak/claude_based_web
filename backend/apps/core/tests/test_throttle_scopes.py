from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.urls import resolve
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import ScopedRateThrottle

from apps.core.tests.test_route_walk import PUBLIC_ALLOWLIST, _resolve_dummy_path

EXPECTED_PUBLIC_SCOPES = {
    "anon_auth",
    "reports",
    "lookups",
    "alerts",
    "public_read",
    "simulator",
}

EXCLUDED_SCHEMA_ROUTES = {
    "/api/v1/health/",
    "/api/v1/health/ready/",
    "/api/v1/schema/",
    "/api/v1/docs/",
    "/api/v1/redoc/",
}


def test_all_public_endpoints_declare_valid_throttle_scope():
    """
    D142: Every public API endpoint (outside raw health checks and schema)
    must explicitly declare a valid non-empty throttle_scope.
    """
    public_routes = [r for r in PUBLIC_ALLOWLIST if r not in EXCLUDED_SCHEMA_ROUTES]
    assert len(public_routes) >= 15, "Expected public routes in PUBLIC_ALLOWLIST"

    for raw_route in sorted(public_routes):
        concrete_path = _resolve_dummy_path(raw_route)
        match = resolve(concrete_path)
        view_cls = getattr(match.func, "cls", None) or getattr(match.func, "view_class", None)
        assert view_cls is not None, f"Could not determine view class for {raw_route}"

        assert hasattr(view_cls, "throttle_scope"), (
            f"Public view {view_cls.__name__} for route '{raw_route}' must define 'throttle_scope'"
        )
        scope = view_cls.throttle_scope
        assert bool(scope), f"throttle_scope on {view_cls.__name__} cannot be empty"
        assert scope in EXPECTED_PUBLIC_SCOPES, (
            f"throttle_scope '{scope}' on {view_cls.__name__} not in expected scopes {EXPECTED_PUBLIC_SCOPES}"
        )


def test_throttle_rates_configured_in_base_settings():
    """
    Ensure all declared throttle scopes have configured rates in REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].
    """
    rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
    for scope in EXPECTED_PUBLIC_SCOPES:
        assert scope in rates, f"Expected throttle rate configuration for scope '{scope}' in base settings"
        assert "/" in rates[scope], f"Rate format invalid for '{scope}': {rates[scope]}"


def test_scoped_rate_throttle_recognizes_scope():
    """
    Verify ScopedRateThrottle correctly extracts scope and evaluates rate limit logic.
    """
    from rest_framework.views import APIView

    class DummyThrottledView(APIView):
        throttle_scope = "public_read"

    factory = APIRequestFactory()
    request = factory.get("/dummy/")
    request.user = AnonymousUser()

    throttle = ScopedRateThrottle()
    view = DummyThrottledView()

    assert throttle.get_cache_key(request, view) is not None
