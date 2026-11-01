from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

# Read .env from repo root (parent of backend) if present
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-dev-key-for-phase-1b-local-only")
DEBUG = env("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.intel.apps.IntelConfig",
    "apps.alerts.apps.AlertsConfig",
    "apps.broadcasts.apps.BroadcastsConfig",
    "apps.literacy.apps.LiteracyConfig",
    "apps.scanner.apps.ScannerAppConfig",
    "apps.ops.apps.OpsConfig",
]

AUTH_USER_MODEL = "accounts.User"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="scamshield"),
        "USER": env("DB_USER", default="scamshield_user"),
        "PASSWORD": env("DB_PASSWORD", default="scamshield_password"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 10,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Security keys & IP hashing (D2, D49)
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY", default="dev-jwt-signing-key-scamshield-auth")
HMAC_IP_SALT = env("HMAC_IP_SALT", default="dev-hmac-ip-salt-scamshield")
TRUSTED_PROXY_HOPS = env.int("TRUSTED_PROXY_HOPS", default=1)

# SimpleJWT configuration (D49)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Refresh cookie configuration (D43)
REFRESH_COOKIE_NAME = "refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth/"
REFRESH_COOKIE_SAMESITE = "Lax"
REFRESH_COOKIE_HTTPONLY = True
REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600
REFRESH_COOKIE_SECURE = env.bool("REFRESH_COOKIE_SECURE", default=False)

# DRF configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.ScamShieldJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.errors.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ScamShield API",
    "DESCRIPTION": "ScamShield Cloud Platform REST API (University Cloud Project CT071-3-3-DDAC)",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "StaffRegistrationRoleEnum": ["ANALYST", "EDUCATOR"],
    },
}

ROOT_URLCONF = "config.urls"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
