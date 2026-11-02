import hashlib
from datetime import timedelta

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.throttling import BaseThrottle

from apps.core import audit, metrics
from apps.core.ip import client_ip_hash
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog


def _ip_hash_to_lock_id(ip_hash: str) -> int:
    """Converts the first 16 hex chars of ip_hash into a 64-bit signed integer for pg_advisory_lock."""
    if not ip_hash:
        return 0
    try:
        val = int(ip_hash[:16], 16)
    except ValueError:
        val = int(hashlib.sha256(ip_hash.encode("utf-8")).hexdigest()[:16], 16)

    if val >= (1 << 63):
        val -= (1 << 64)
    return val


def check_report_submission_throttle(ip_hash: str, user=None) -> None:
    """
    D47, D63, D139: Checks report submission rate limits from the audit table:
    - Anonymous / unlinked: max 5 reports per ip_hash per hour.
    - Logged-in: max 20 reports per user per hour.
    - Uses PostgreSQL advisory lock on ip_hash for atomic check-and-insert under concurrent bursts.
    Over the limit: writes RATE_LIMIT_BLOCK, emits metric, raises exceptions.Throttled.
    """
    lock_id = _ip_hash_to_lock_id(ip_hash) if ip_hash and connection.vendor == "postgresql" else None
    if lock_id is not None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [lock_id])

    try:
        now = timezone.now()
        cutoff = now - timedelta(hours=1)

        if user and user.is_authenticated:
            count = SystemAuditLog.objects.filter(
                event_type=AuditEventType.REPORT_SUBMITTED,
                actor=user,
                occurred_at__gte=cutoff,
            ).count()
            if count >= 20:
                audit.log_event(
                    event_type=AuditEventType.RATE_LIMIT_BLOCK,
                    actor=user,
                    ip_hash=ip_hash,
                    target=("USER", str(user.id)),
                    metadata={"action": "report_submission", "threshold": 20},
                    severity=AuditSeverity.WARN,
                )
                metrics.emit("RateLimitBlocks", 1)
                raise exceptions.Throttled(
                    wait=3600,
                    detail="Report submission rate limit exceeded for this account. Maximum 20 reports per hour.",
                )
        else:
            if not ip_hash:
                return
            count = SystemAuditLog.objects.filter(
                event_type=AuditEventType.REPORT_SUBMITTED,
                actor__isnull=True,
                actor_ip_hash=ip_hash,
                occurred_at__gte=cutoff,
            ).count()
            if count >= 5:
                audit.log_event(
                    event_type=AuditEventType.RATE_LIMIT_BLOCK,
                    ip_hash=ip_hash,
                    metadata={"action": "report_submission", "threshold": 5},
                    severity=AuditSeverity.WARN,
                )
                metrics.emit("RateLimitBlocks", 1)
                raise exceptions.Throttled(
                    wait=3600,
                    detail="Report submission rate limit exceeded from this IP address. Maximum 5 reports per hour.",
                )
    finally:
        if lock_id is not None:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])


def check_report_tracking_throttle(ip_hash: str) -> None:
    """
    D47, D63: Checks tracking failure limit:
    - Max 10 failed tracking attempts per ip_hash per 15 minutes.
    Over limit: writes RATE_LIMIT_BLOCK, emits metric, raises exceptions.Throttled.
    """
    if not ip_hash:
        return

    now = timezone.now()
    cutoff = now - timedelta(minutes=15)
    count = SystemAuditLog.objects.filter(
        event_type=AuditEventType.REPORT_TRACK_FAILED,
        actor_ip_hash=ip_hash,
        occurred_at__gte=cutoff,
    ).count()

    if count >= 10:
        audit.log_event(
            event_type=AuditEventType.RATE_LIMIT_BLOCK,
            ip_hash=ip_hash,
            metadata={"action": "report_tracking", "threshold": 10},
            severity=AuditSeverity.WARN,
        )
        metrics.emit("RateLimitBlocks", 1)
        raise exceptions.Throttled(
            wait=900,
            detail="Too many failed report tracking attempts. Please wait 15 minutes.",
        )


def check_lookup_throttle(ip_hash: str) -> None:
    """
    Rate-limits public threat lookups: max 30 requests per minute per IP hash (D103).
    Over the limit: writes RATE_LIMIT_BLOCK audit log, emits RateLimitBlocks metric,
    and raises exceptions.Throttled(wait=60).
    """
    if not ip_hash:
        return

    cache_key = f"throttle:lookup:{ip_hash}"
    count = cache.get(cache_key, 0)
    if count >= 30:
        audit.log_event(
            event_type=AuditEventType.RATE_LIMIT_BLOCK,
            actor=None,
            ip_hash=ip_hash,
            metadata={"action": "lookup", "threshold": 30},
            severity=AuditSeverity.WARN,
        )
        metrics.emit("RateLimitBlocks", 1)
        raise exceptions.Throttled(
            wait=60,
            detail="Lookup rate limit exceeded. Maximum 30 requests per minute.",
        )

    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=60)


class LookupRateThrottle(BaseThrottle):
    def allow_request(self, request, view):
        ip_hash = client_ip_hash(request)
        check_lookup_throttle(ip_hash)
        return True
