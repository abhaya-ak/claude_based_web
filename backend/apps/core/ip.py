import hashlib
import hmac

from django.conf import settings
from django.http import HttpRequest


def client_ip_hash(request: HttpRequest) -> str:
    """
    Extracts client IP from X-Forwarded-For at TRUSTED_PROXY_HOPS depth,
    falling back to REMOTE_ADDR. Computes HMAC-SHA256 hex digest using HMAC_IP_SALT.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        parts = [p.strip() for p in x_forwarded_for.split(",") if p.strip()]
        hops = getattr(settings, "TRUSTED_PROXY_HOPS", 1)
        if len(parts) >= hops:
            raw_ip = parts[-hops]
        else:
            raw_ip = parts[0]
    else:
        raw_ip = request.META.get("REMOTE_ADDR", "127.0.0.1")

    salt = getattr(settings, "HMAC_IP_SALT", "default-salt").encode("utf-8")
    return hmac.new(salt, raw_ip.encode("utf-8"), hashlib.sha256).hexdigest()
