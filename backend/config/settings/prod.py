import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

# Production enforces DEBUG = False unconditionally
if env.bool("DEBUG", default=False) or os.environ.get("DEBUG", "").lower() in ("true", "1"):  # noqa: F405
    raise ImproperlyConfigured("DEBUG must be False in production.")
DEBUG = False

# Validate DJANGO_SECRET_KEY
secret_key = os.environ.get("DJANGO_SECRET_KEY")
if not secret_key:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")
if len(secret_key) < 50:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be at least 50 characters in production.")
if secret_key.startswith("django-insecure"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must not use 'django-insecure' prefix in production.")
SECRET_KEY = secret_key

# Validate JWT_SIGNING_KEY
jwt_key = os.environ.get("JWT_SIGNING_KEY")
if not jwt_key:
    raise ImproperlyConfigured("JWT_SIGNING_KEY must be set in production.")
if len(jwt_key) < 32:
    raise ImproperlyConfigured("JWT_SIGNING_KEY must be at least 32 characters in production.")
JWT_SIGNING_KEY = jwt_key

# Validate HMAC_IP_SALT
ip_salt = os.environ.get("HMAC_IP_SALT")
if not ip_salt:
    raise ImproperlyConfigured("HMAC_IP_SALT must be set in production.")
if len(ip_salt) < 32:
    raise ImproperlyConfigured("HMAC_IP_SALT must be at least 32 characters in production.")
HMAC_IP_SALT = ip_salt

# Validate INDICATOR_HMAC_KEY
indicator_key = os.environ.get("INDICATOR_HMAC_KEY")
if not indicator_key:
    raise ImproperlyConfigured("INDICATOR_HMAC_KEY must be set in production.")
if len(indicator_key) < 32:
    raise ImproperlyConfigured("INDICATOR_HMAC_KEY must be at least 32 characters in production.")
INDICATOR_HMAC_KEY = indicator_key

# Validate ALLOWED_HOSTS
raw_hosts = os.environ.get("ALLOWED_HOSTS", "")
valid_hosts = [h.strip() for h in raw_hosts.split(",") if h.strip()]
if not valid_hosts:
    raise ImproperlyConfigured("ALLOWED_HOSTS cannot be empty in production.")
ALLOWED_HOSTS = valid_hosts

# Validate PUBLIC_BASE_URL
base_url = (os.environ.get("PUBLIC_BASE_URL") or "").strip()
if not base_url:
    raise ImproperlyConfigured("PUBLIC_BASE_URL must be set in production.")
PUBLIC_BASE_URL = base_url

# Validate TRUSTED_PROXY_HOPS
raw_hops = os.environ.get("TRUSTED_PROXY_HOPS")
if raw_hops is None:
    raise ImproperlyConfigured("TRUSTED_PROXY_HOPS must be set in production.")
try:
    hops = int(raw_hops)
    if hops < 0:
        raise ValueError("Must be non-negative")
except (ValueError, TypeError) as exc:
    raise ImproperlyConfigured("TRUSTED_PROXY_HOPS must be an integer >= 0 in production.") from exc
TRUSTED_PROXY_HOPS = hops

# Validate Database Credentials
for db_var in ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"):
    val = os.environ.get(db_var)
    if not val or not val.strip():
        raise ImproperlyConfigured(f"{db_var} must be set in production.")

db_sslmode = os.environ.get("DB_SSLMODE", "require")
DATABASES["default"]["NAME"] = os.environ["DB_NAME"]  # noqa: F405
DATABASES["default"]["USER"] = os.environ["DB_USER"]  # noqa: F405
DATABASES["default"]["PASSWORD"] = os.environ["DB_PASSWORD"]  # noqa: F405
DATABASES["default"]["HOST"] = os.environ["DB_HOST"]  # noqa: F405
DATABASES["default"]["PORT"] = os.environ["DB_PORT"]  # noqa: F405
DATABASES["default"]["CONN_MAX_AGE"] = 60  # noqa: F405
DATABASES["default"]["ATOMIC_REQUESTS"] = False  # noqa: F405
DATABASES["default"]["OPTIONS"]["sslmode"] = db_sslmode  # noqa: F405
DATABASES["default"]["OPTIONS"]["options"] = "-c statement_timeout=10000"  # noqa: F405

# Production security and deploy check compliance
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# API documentation UI disabled in production per Decision D37
ENABLE_API_DOCS = False

# Silenced system checks per Rule R-D5 / Decision D36:
# HTTPS and HSTS terminate at CloudFront / ALB.
SILENCED_SYSTEM_CHECKS = [
    "security.W004",  # SECURE_HSTS_SECONDS
    "security.W008",  # SECURE_SSL_REDIRECT
]
