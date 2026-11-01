import hashlib
import hmac
import ipaddress

from django.conf import settings
from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str:
    """Extracts client IP from request respecting TRUSTED_PROXY_HOPS setting."""
    remote_addr = request.META.get("REMOTE_ADDR", "").strip()
    hops = getattr(settings, "TRUSTED_PROXY_HOPS", 0)

    if hops <= 0:
        return remote_addr

    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if not xff:
        return remote_addr

    ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
    target_idx = -(hops + 1)
    try:
        candidate = ips[target_idx]
    except IndexError:
        candidate = ips[0] if ips else remote_addr

    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        return remote_addr


def client_ip_hash(request: HttpRequest) -> str:
    """Returns 64-hex HMAC-SHA256 of client IP using HMAC_IP_SALT."""
    ip = get_client_ip(request)
    salt = getattr(settings, "HMAC_IP_SALT", "").encode("utf-8")
    return hmac.new(salt, ip.encode("utf-8"), hashlib.sha256).hexdigest()
