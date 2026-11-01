from .base import *  # noqa: F403

DEBUG = False

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

TRUSTED_PROXY_HOPS = 0
METRICS_ENABLED = False
SECRET_KEY = "test-secret-key-for-scamshield-tests-must-be-long-enough-12345"
JWT_SIGNING_KEY = "test-jwt-signing-key-32-chars-long!"
HMAC_IP_SALT = "test-hmac-ip-salt-32-chars-long-!"
INDICATOR_HMAC_KEY = "test-indicator-hmac-key-32-char-!"
EVIDENCE_BUCKET = "scamshield-evidence-test"
PUBLIC_BASE_URL = "http://testserver"
