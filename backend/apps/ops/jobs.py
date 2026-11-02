import logging
from datetime import timedelta

from django.conf import settings
from django.db import connection, models, transaction
from django.utils import timezone

from apps.core.jobs.registry import register_job
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog
from apps.ops.services.cloudwatch_service import put_metrics
from apps.reports.models import ScamReport

logger = logging.getLogger(__name__)

SECURITY_EVENT_TYPES = {
    AuditEventType.RATE_LIMIT_BLOCK.value,
    AuditEventType.LOGIN_FAILURE.value,
    AuditEventType.STAFF_REGISTERED.value,
    AuditEventType.ROLE_APPROVED.value,
    AuditEventType.ROLE_REJECTED.value,
    AuditEventType.ROLE_CHANGED.value,
    AuditEventType.PASSWORD_CHANGED.value,
    AuditEventType.REPORT_REJECTED.value,
    AuditEventType.INDICATOR_REVOKED.value,
    AuditEventType.SCAN_FAILED.value,
    AuditEventType.REPORT_TRACK_FAILED.value,
}


@register_job("aggregate_ops_metrics")
def aggregate_ops_metrics() -> str:
    """
    Computes hourly aggregate counts of business actions from the database and pushes
    them to CloudWatch as a fallback if immediate per-request emits were dropped.
    Protected by Postgres advisory lock.
    """
    now = timezone.now()
    since = now - timedelta(hours=1)
    env_name = getattr(settings, "ENVIRONMENT", "production")

    # 1. Reports counts
    reports_count = ScamReport.objects.filter(created_at__gte=since).count()
    high_priority_count = ScamReport.objects.filter(created_at__gte=since, is_high_priority=True).count()

    # 2. Audit logs counts
    rate_limit_count = SystemAuditLog.objects.filter(
        event_type=AuditEventType.RATE_LIMIT_BLOCK.value,
        occurred_at__gte=since,
    ).count()

    login_failures_count = SystemAuditLog.objects.filter(
        event_type=AuditEventType.LOGIN_FAILURE.value,
        occurred_at__gte=since,
    ).count()

    alerts_published_count = SystemAuditLog.objects.filter(
        event_type=AuditEventType.ADVISORY_PUBLISHED.value,
        occurred_at__gte=since,
    ).count()

    scan_failures_count = SystemAuditLog.objects.filter(
        event_type=AuditEventType.SCAN_FAILED.value,
        occurred_at__gte=since,
    ).count()

    metric_payload = [
        {"name": "ReportsSubmitted", "value": float(reports_count), "dims": {"Environment": env_name}},
        {"name": "ReportsHighPriority", "value": float(high_priority_count), "dims": {"Environment": env_name}},
        {"name": "RateLimitBlocks", "value": float(rate_limit_count), "dims": {"Environment": env_name}},
        {"name": "LoginFailures", "value": float(login_failures_count), "dims": {"Environment": env_name}},
        {"name": "AlertsPublished", "value": float(alerts_published_count), "dims": {"Environment": env_name}},
        {"name": "ScanFailures", "value": float(scan_failures_count), "dims": {"Environment": env_name}},
    ]

    success = put_metrics(metric_payload)
    status_str = "success" if success else "failed"

    summary = (
        f"Aggregated metrics pushed ({status_str}): reports={reports_count}, "
        f"high_priority={high_priority_count}, rate_limits={rate_limit_count}, "
        f"login_failures={login_failures_count}, alerts={alerts_published_count}, "
        f"scan_failures={scan_failures_count}"
    )
    logger.info(summary)
    return summary


@register_job("purge_expired_audit_logs")
def purge_expired_audit_logs() -> int:
    """
    Purges expired audit logs according to retention rules (03a §8, D125, D126):
    - INFO severity non-security rows older than 90 days are deleted.
    - WARN / ALERT and security event rows older than 365 days are deleted.
    Enforces authorization via session setting 'scamshield.audit_purge_allowed = on'.
    Runs under Postgres advisory lock. Returns count of purged rows.
    """
    now = timezone.now()
    info_cutoff = now - timedelta(days=90)
    security_cutoff = now - timedelta(days=365)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL scamshield.audit_purge_allowed = 'on';")
            cursor.execute("SET scamshield.audit_purge_allowed = 'on';")

        try:
            info_deleted, _ = (
                SystemAuditLog.objects.filter(
                    occurred_at__lt=info_cutoff,
                    severity=AuditSeverity.INFO.value,
                )
                .exclude(event_type__in=SECURITY_EVENT_TYPES)
                .delete()
            )

            sec_deleted, _ = (
                SystemAuditLog.objects.filter(occurred_at__lt=security_cutoff)
                .filter(
                    models.Q(severity__in=[AuditSeverity.WARN.value, AuditSeverity.ALERT.value])
                    | models.Q(event_type__in=SECURITY_EVENT_TYPES)
                )
                .delete()
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SET scamshield.audit_purge_allowed = 'off';")

    total_purged = info_deleted + sec_deleted
    logger.info(
        "Purged %d expired audit logs (%d INFO >90d, %d security >365d)",
        total_purged,
        info_deleted,
        sec_deleted,
    )
    return total_purged
