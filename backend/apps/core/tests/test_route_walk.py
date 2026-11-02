import re
import uuid

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

PUBLIC_ALLOWLIST = {
    "/api/v1/health/",
    "/api/v1/health/ready/",
    "/api/v1/schema/",
    "/api/v1/docs/",
    "/api/v1/redoc/",
    "/api/v1/auth/register/",
    "/api/v1/auth/register/staff/",
    "/api/v1/auth/login/",
    "/api/v1/auth/refresh/",
    "/api/v1/auth/logout/",
    "/api/v1/reports/options/",
    "/api/v1/reports/",
    "/api/v1/reports/track/",
    "/api/v1/lookups/",
    "/api/v1/alerts/subscriptions/",
    "/api/v1/alerts/subscriptions/confirm/",
    "/api/v1/alerts/subscriptions/unsubscribe/",
}

MACHINE_HMAC_ALLOWLIST = {
    "/api/v1/internal/scan-results/",
}


def _collect_routes(patterns=None, prefix=""):
    """Recursively collect all endpoint paths from Django URL resolver."""
    if patterns is None:
        patterns = get_resolver().url_patterns

    routes = []
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            routes.extend(_collect_routes(pattern.url_patterns, prefix + str(pattern.pattern)))
        elif isinstance(pattern, URLPattern):
            raw_path = "/" + prefix + str(pattern.pattern)
            routes.append((raw_path, pattern))
    return routes


def _resolve_dummy_path(raw_path):
    """Replace pattern parameters like <uuid:pk> or <int:id> with dummy concrete values."""
    resolved = re.sub(r"<uuid:[^>]+>", str(uuid.uuid4()), raw_path)
    resolved = re.sub(r"<int:[^>]+>", "1", resolved)
    resolved = re.sub(r"<(?:str|slug):[^>]+>", "test", resolved)
    resolved = re.sub(r"<[^>]+>", "test", resolved)
    return resolved


@pytest.mark.django_db
class TestRouteWalkAndPublicAllowlist:
    """
    R-A3: Route-walk test.
    Ensures every route under /api/v1/ requires authentication (returns 401)
    unless explicitly present in PUBLIC_ALLOWLIST or MACHINE_HMAC_ALLOWLIST.
    Never returns 500 when called anonymously.
    """

    def test_all_api_v1_endpoints_enforce_auth_unless_whitelisted(self):
        client = APIClient()
        all_routes = _collect_routes()

        api_v1_routes = [(raw, pat) for raw, pat in all_routes if raw.startswith("/api/v1/")]
        assert len(api_v1_routes) > 0, "No /api/v1/ routes discovered"

        for raw_path, _pattern in api_v1_routes:
            is_allowlisted = raw_path in PUBLIC_ALLOWLIST or any(
                allowed == raw_path for allowed in PUBLIC_ALLOWLIST
            )
            is_hmac_allowlisted = raw_path in MACHINE_HMAC_ALLOWLIST or any(
                allowed == raw_path for allowed in MACHINE_HMAC_ALLOWLIST
            )

            concrete_path = _resolve_dummy_path(raw_path)

            # Test GET
            response_get = client.get(concrete_path)
            assert response_get.status_code != 500, (
                f"Anonymous GET {concrete_path} resulted in 500 Server Error"
            )

            # Test POST
            response_post = client.post(concrete_path, data={}, format="json")
            assert response_post.status_code != 500, (
                f"Anonymous POST {concrete_path} resulted in 500 Server Error"
            )

            if is_hmac_allowlisted:
                assert response_post.status_code == 403, (
                    f"Machine HMAC route {raw_path} without headers did not return 403"
                )
                assert response_post.data.get("error", {}).get("code") == "permission_denied"
            elif not is_allowlisted:
                codes = {response_get.status_code, response_post.status_code}
                assert 401 in codes, (
                    f"Non-allowlisted route {raw_path} (concrete: {concrete_path}) "
                    f"did not return 401 when accessed anonymously. Statuses: GET={response_get.status_code}, POST={response_post.status_code}"
                )
            else:
                codes = {response_get.status_code, response_post.status_code}
                assert 401 not in codes, (
                    f"Allowlisted route {raw_path} unexpectedly returned 401 Unauthorized"
                )

    def test_allowlist_matches_known_public_routes_strictly(self):
        """Verify that every route in PUBLIC_ALLOWLIST exists in the URL patterns."""
        all_routes = [raw for raw, _ in _collect_routes()]
        required_public = {
            "/api/v1/health/",
            "/api/v1/health/ready/",
            "/api/v1/schema/",
            "/api/v1/docs/",
            "/api/v1/redoc/",
            "/api/v1/auth/register/",
            "/api/v1/auth/register/staff/",
            "/api/v1/auth/login/",
            "/api/v1/auth/refresh/",
            "/api/v1/auth/logout/",
            "/api/v1/reports/options/",
            "/api/v1/reports/",
            "/api/v1/reports/track/",
        }
        for route in required_public:
            assert route in all_routes, f"Expected public route {route} not found in URLconf"
