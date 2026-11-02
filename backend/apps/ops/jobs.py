import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.core.jobs.registry import register_job
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.ops.services.cloudwatch_service import put_metrics
from apps.reports.models import ScamReport

logger = logging.getLogger(__name__)


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
