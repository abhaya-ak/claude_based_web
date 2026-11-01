from .base import *  # noqa: F403

DEBUG = True
TRUSTED_PROXY_HOPS = 0
METRICS_ENABLED = False
INDICATOR_HMAC_KEY = env("INDICATOR_HMAC_KEY", default="dev-indicator-hmac-key-placeholder-32-chars")  # noqa: F405
EVIDENCE_BUCKET = env("EVIDENCE_BUCKET", default="scamshield-evidence-dev")  # noqa: F405
