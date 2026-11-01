from datetime import timedelta

from django.utils import timezone
from rest_framework import exceptions

from apps.core import audit, metrics
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog


def check_report_submission_throttle(ip_hash: str, user=None) -> None:
    """
    D47, D63: Checks report submission rate limits from the audit table:
    - Anonymous / unlinked: max 5 reports per ip_hash per hour.
    - Logged-in: max 20 reports per user per hour.
    Over the limit: writes RATE_LIMIT_BLOCK, emits metric, raises exceptions.Throttled.
    """
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
