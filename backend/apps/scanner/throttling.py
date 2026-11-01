import logging

from django.core.cache import cache
from rest_framework import exceptions
from rest_framework.throttling import BaseThrottle

from apps.core import audit, metrics
from apps.core.ip import client_ip_hash
from apps.ops.models import AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


def check_scanner_callback_throttle(ip_hash: str) -> None:
    """
    Rate-limits the internal callback endpoint: 100 requests per minute per IP hash (D90).
    Over the limit: writes RATE_LIMIT_BLOCK audit log, emits RateLimitBlocks metric,
    and raises exceptions.Throttled(wait=60).
    """
    if not ip_hash:
        return

    cache_key = f"throttle:scanner_callback:{ip_hash}"
    count = cache.get(cache_key, 0)
    if count >= 100:
        audit.log_event(
            event_type=AuditEventType.RATE_LIMIT_BLOCK,
            actor=None,
            ip_hash=ip_hash,
            metadata={"action": "scanner_callback", "threshold": 100},
            severity=AuditSeverity.WARN,
        )
        metrics.emit("RateLimitBlocks", 1)
        raise exceptions.Throttled(
            wait=60,
            detail="Scanner callback rate limit exceeded. Maximum 100 requests per minute.",
        )

    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=60)


class ScannerCallbackThrottle(BaseThrottle):
    def allow_request(self, request, view):
        ip_hash = client_ip_hash(request)
        check_scanner_callback_throttle(ip_hash)
        return True
