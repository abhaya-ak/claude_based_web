from datetime import timedelta

from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.core.audit import log_event
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog


def check_login_failure_throttle(ip_hash: str, target_user: User | None = None) -> None:
    """
    D47: Checks login failure throttles against the audit table:
    - Max 10 LOGIN_FAILURE events per ip_hash in the last 15 minutes.
    - Max 10 LOGIN_FAILURE events per target account in the last 15 minutes.
    Over the limit: writes RATE_LIMIT_BLOCK and raises exceptions.Throttled(wait=900).
    """
    cutoff = timezone.now() - timedelta(minutes=15)

    # 1. IP failure check
    if ip_hash:
        ip_count = SystemAuditLog.objects.filter(
            event_type=AuditEventType.LOGIN_FAILURE,
            actor_ip_hash=ip_hash,
            occurred_at__gte=cutoff,
        ).count()
        if ip_count >= 10:
            log_event(
                event_type=AuditEventType.RATE_LIMIT_BLOCK,
                ip_hash=ip_hash,
                metadata={"reason": "login_failure_ip_limit", "threshold": 10},
                severity=AuditSeverity.WARN,
            )
            raise exceptions.Throttled(
                wait=900,
                detail="Too many failed login attempts from this IP address.",
            )

    # 2. Account failure check
    if target_user is not None and getattr(target_user, "id", None) is not None:
        user_id_str = str(target_user.id)
        account_count = SystemAuditLog.objects.filter(
            event_type=AuditEventType.LOGIN_FAILURE,
            target_type="USER",
            target_id=user_id_str,
            occurred_at__gte=cutoff,
        ).count()
        if account_count >= 10:
            log_event(
                event_type=AuditEventType.RATE_LIMIT_BLOCK,
                ip_hash=ip_hash,
                target=("USER", user_id_str),
                metadata={"reason": "login_failure_account_limit", "threshold": 10},
                severity=AuditSeverity.WARN,
            )
            raise exceptions.Throttled(
                wait=900,
                detail="Too many failed login attempts for this user account.",
            )


def check_registration_throttle(ip_hash: str) -> None:
    """
    D47: Checks registration limit:
    - Max 10 registration events (USER_REGISTERED + STAFF_REGISTERED) per ip_hash per hour.
    Over the limit: writes RATE_LIMIT_BLOCK and raises exceptions.Throttled(wait=3600).
    """
    if not ip_hash:
        return

    cutoff = timezone.now() - timedelta(hours=1)
    reg_count = SystemAuditLog.objects.filter(
        event_type__in=[AuditEventType.USER_REGISTERED, AuditEventType.STAFF_REGISTERED],
        actor_ip_hash=ip_hash,
        occurred_at__gte=cutoff,
    ).count()

    if reg_count >= 10:
        log_event(
            event_type=AuditEventType.RATE_LIMIT_BLOCK,
            ip_hash=ip_hash,
            metadata={"reason": "registration_ip_limit", "threshold": 10},
            severity=AuditSeverity.WARN,
        )
        raise exceptions.Throttled(
            wait=3600,
            detail="Too many registration attempts from this IP address.",
        )
