import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core import audit, metrics
from apps.core.jobs.registry import register_job
from apps.ops.models import AuditEventType, AuditSeverity
from apps.reports.models import ScamReport, ScanStatus
from apps.scanner.services.scanner_service import dispatch_scan

logger = logging.getLogger(__name__)

RECOVERY_BATCH_CAP = 100
MAX_SCAN_ATTEMPTS = 5


@register_job("redispatch_pending_scans")
def redispatch_pending_scans() -> dict:
    """
    Background recovery job for pending scans (D92).
    - Discovers ScamReports with scan_status='PENDING' and
      (scan_dispatched_at IS NULL or scan_dispatched_at <= now() - 5m).
    - If scan_attempts < 5: re-dispatches scan.
    - If scan_attempts >= 5: marks scan_status='FAILED', writes SCAN_FAILED audit log,
      and emits ScansFailed metric.
    """
    now = timezone.now()
    cutoff = now - timedelta(minutes=5)

    stalled_reports = (
        ScamReport.objects.filter(scan_status=ScanStatus.PENDING)
        .filter(Q(scan_dispatched_at__isnull=True) | Q(scan_dispatched_at__lte=cutoff))
        .order_by("created_at")[:RECOVERY_BATCH_CAP]
    )

    redispatched_count = 0
    failed_count = 0

    for report in stalled_reports:
        if report.scan_attempts < MAX_SCAN_ATTEMPTS:
            try:
                dispatch_scan(report.id)
                redispatched_count += 1
            except Exception as exc:
                logger.warning("Failed to redispatch scan for report %s: %s", report.id, exc)
        else:
            with transaction.atomic():
                report.scan_status = ScanStatus.FAILED
                report.save(update_fields=["scan_status", "updated_at"])
                audit.log_event(
                    event_type=AuditEventType.SCAN_FAILED,
                    actor=None,
                    target=("REPORT", str(report.id)),
                    severity=AuditSeverity.WARN,
                    metadata={"scan_attempts": report.scan_attempts},
                )
                metrics.emit("ScansFailed", 1)
            failed_count += 1

    return {
        "redispatched": redispatched_count,
        "failed": failed_count,
        "total_processed": redispatched_count + failed_count,
    }
