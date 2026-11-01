from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

# Enforce secure cookie in production (D43)
REFRESH_COOKIE_SECURE = env.bool("REFRESH_COOKIE_SECURE", default=True)  # noqa: F405
if not REFRESH_COOKIE_SECURE:
    raise ImproperlyConfigured("REFRESH_COOKIE_SECURE must be True in production.")

# Secret checks in production
if SECRET_KEY == "django-insecure-dev-key-for-phase-1b-local-only":  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")

if JWT_SIGNING_KEY == "dev-jwt-signing-key-scamshield-auth":  # noqa: F405
    raise ImproperlyConfigured("JWT_SIGNING_KEY must be set in production.")
