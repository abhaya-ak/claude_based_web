from django.conf import settings
from django.http import Http404, JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.views import health_liveness, health_readiness


def _extract_request_id(request) -> str:
    if not request:
        return ""
    return (
        getattr(request, "correlation_id", None)
        or getattr(request, "id", None)
        or (request.headers.get("x-request-id") if hasattr(request, "headers") else None)
        or request.META.get("HTTP_X_REQUEST_ID", "")
    )


def bad_request_handler(request, exception=None):
    return JsonResponse(
        {
            "error": {
                "code": "BAD_REQUEST",
                "message": "Bad request.",
                "details": None,
                "request_id": _extract_request_id(request),
            }
        },
        status=400,
    )


def permission_denied_handler(request, exception=None):
    return JsonResponse(
        {
            "error": {
                "code": "PERMISSION_DENIED",
                "message": "Permission denied.",
                "details": None,
                "request_id": _extract_request_id(request),
            }
        },
        status=403,
    )


def not_found_handler(request, exception=None):
    return JsonResponse(
        {
            "error": {
                "code": "NOT_FOUND",
                "message": "Not found.",
                "details": None,
                "request_id": _extract_request_id(request),
            }
        },
        status=404,
    )


def server_error_handler(request):
    return JsonResponse(
        {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "details": None,
                "request_id": _extract_request_id(request),
            }
        },
        status=500,
    )


class ProtectedSpectacularAPIView(SpectacularAPIView):
    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "ENABLE_API_DOCS", True):
            raise Http404("API documentation is disabled.")
        return super().dispatch(request, *args, **kwargs)


class ProtectedSpectacularSwaggerView(SpectacularSwaggerView):
    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "ENABLE_API_DOCS", True):
            raise Http404("API documentation is disabled.")
        return super().dispatch(request, *args, **kwargs)


class ProtectedSpectacularRedocView(SpectacularRedocView):
    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "ENABLE_API_DOCS", True):
            raise Http404("API documentation is disabled.")
        return super().dispatch(request, *args, **kwargs)


handler400 = "config.urls.bad_request_handler"
handler403 = "config.urls.permission_denied_handler"
handler404 = "config.urls.not_found_handler"
handler500 = "config.urls.server_error_handler"

urlpatterns = [
    path("api/v1/health/", health_liveness, name="health-liveness"),
    path("api/v1/health/ready/", health_readiness, name="health-readiness"),
    path("api/v1/schema/", ProtectedSpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", ProtectedSpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/redoc/", ProtectedSpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/admin-portal/users/", include("apps.accounts.urls_admin")),
    path("api/v1/admin-portal/", include("apps.scanner.urls_admin")),
    path("api/v1/reports/", include("apps.reports.urls")),
    path("api/v1/lookups/", include("apps.reports.urls_lookup")),
    path("api/v1/alerts/", include("apps.alerts.urls")),
    path("api/v1/analytics/", include("apps.broadcasts.urls_analytics")),
    path("api/v1/advisories/", include("apps.broadcasts.urls_advisories")),
    path("api/v1/internal/", include("apps.scanner.urls_internal")),
    path("api/v1/triage/", include("apps.intel.urls")),
]
