import os
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

# Read .env from repo root if present, unless in production settings
settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
if settings_module != "config.settings.prod":
    env_file = BASE_DIR.parent / ".env"
    if env_file.exists():
        environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-dev-key-for-phase-1b-local-only")
DEBUG = env("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

ROOT_URLCONF = "config.urls"
APPEND_SLASH = False

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "drf_spectacular_sidecar",
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

MIDDLEWARE = [
    "apps.core.middleware.HealthCheckMiddleware",
    "apps.core.middleware.CorrelationIdMiddleware",
    "apps.core.middleware.RequestSizeLimitMiddleware",
    "apps.core.middleware.AccessLogMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "accounts.User"

db_options = {
    "options": "-c statement_timeout=10000",
}
sslmode = env("DB_SSLMODE", default=None)
if sslmode:
    db_options["sslmode"] = sslmode

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="scamshield"),
        "USER": env("DB_USER", default="scamshield_user"),
        "PASSWORD": env("DB_PASSWORD", default="scamshield_password"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
        "ATOMIC_REQUESTS": False,
        "OPTIONS": db_options,
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.ScamShieldJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

ENABLE_API_DOCS = True

SPECTACULAR_SETTINGS = {
    "TITLE": "ScamShield API",
    "DESCRIPTION": "Scam reporting, lookup, and literacy platform REST API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "StaffRegisterRoleEnum": [
            ("ANALYST", "Analyst"),
            ("EDUCATOR", "Educator"),
        ],
        "UserRoleEnum": "apps.accounts.models.Role",
        "IndicatorStatusEnum": "apps.intel.models.IndicatorStatus",
        "ReportStatusEnum": "apps.reports.models.ReportStatus",
        "PrimaryCategoryEnum": "apps.reports.models.ScamCategory",
    },
    "APPEND_COMPONENTS": {
        "schemas": {
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"nullable": True},
                            "request_id": {"type": "string"},
                        },
                        "required": ["code", "message", "details", "request_id"],
                    }
                },
                "required": ["error"],
            }
        }
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "pii_scrubber": {
            "()": "apps.core.logging.PiiScrubberFilter",
        },
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["pii_scrubber"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
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

# Upload limits (D57, D58, D71)
FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2.5 MB (spool larger files to disk)
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024 * 1024  # 16 MB request cap

# AWS S3 Evidence Bucket (D58, D60, D75)
EVIDENCE_BUCKET = env("EVIDENCE_BUCKET", default="scamshield-evidence-dev")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Scanner & Lambda Configuration (D87, D88, D89, D90, D91)
SCANNER_LAMBDA_FUNCTION_NAME = env("SCANNER_LAMBDA_FUNCTION_NAME", default="scamshield-heuristic-scanner")
SCANNER_CALLBACK_SECRET = env("SCANNER_CALLBACK_SECRET", default=env("INTERNAL_CALLBACK_HMAC_KEY", default="dev-scanner-callback-secret-placeholder-32-chars-min"))
INTERNAL_CALLBACK_HMAC_KEY = SCANNER_CALLBACK_SECRET
SCANNER_CALLBACK_URL = env("SCANNER_CALLBACK_URL", default="http://localhost:8000/api/v1/internal/scan-results/")
STAFF_TOPIC_ARN = env("STAFF_TOPIC_ARN", default="arn:aws:sns:ap-southeast-1:123456789012:scamshield-staff-alerts")
