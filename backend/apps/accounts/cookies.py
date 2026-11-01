from django.conf import settings
from django.http import HttpRequest, HttpResponse
from rest_framework import exceptions


def set_refresh_cookie(response: HttpResponse, raw_refresh_token: str) -> None:
    """Sets the HttpOnly refresh token cookie on the response per D43."""
    response.set_cookie(
        key=getattr(settings, "REFRESH_COOKIE_NAME", "refresh"),
        value=raw_refresh_token,
        max_age=getattr(settings, "REFRESH_COOKIE_MAX_AGE", 7 * 24 * 3600),
        path=getattr(settings, "REFRESH_COOKIE_PATH", "/api/v1/auth/"),
        domain=None,
        secure=getattr(settings, "REFRESH_COOKIE_SECURE", False),
        httponly=getattr(settings, "REFRESH_COOKIE_HTTPONLY", True),
        samesite=getattr(settings, "REFRESH_COOKIE_SAMESITE", "Lax"),
    )


def clear_refresh_cookie(response: HttpResponse) -> None:
    """Clears the refresh token cookie from the client per D43."""
    response.delete_cookie(
        key=getattr(settings, "REFRESH_COOKIE_NAME", "refresh"),
        path=getattr(settings, "REFRESH_COOKIE_PATH", "/api/v1/auth/"),
        samesite=getattr(settings, "REFRESH_COOKIE_SAMESITE", "Lax"),
    )


def require_csrf_header(request: HttpRequest) -> None:
    """Enforces X-Requested-With: scamshield-web header per D44."""
    header_val = request.headers.get("X-Requested-With")
    if header_val != "scamshield-web":
        raise exceptions.PermissionDenied(
            detail="Missing or invalid X-Requested-With header.",
            code="permission_denied",
        )
