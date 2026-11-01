from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import connections
from django.utils import timezone

from apps.core.jobs.registry import get_lock_id_for_job
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog
from apps.reports.models import ReportStatus, ScamCategory, ScamReport, ScanStatus
from apps.scanner.jobs import redispatch_pending_scans


@pytest.mark.django_db
class TestRedispatchPendingScansJob:
    def _create_report(
        self,
        reference: str,
        scan_status: str = ScanStatus.PENDING,
        scan_attempts: int = 1,
        scan_dispatched_at=None,
    ) -> ScamReport:
        return ScamReport.objects.create(
            reference_code=reference,
            category=ScamCategory.OTHER,
            country_code="MY",
            currency="MYR",
            financial_loss=0,
            message_text="Test stalled scan message",
            platform="SMS",
            status=ReportStatus.PENDING,
            scan_status=scan_status,
            scan_attempts=scan_attempts,
            scan_dispatched_at=scan_dispatched_at,
        )

    def test_recent_pending_dispatched_under_5_min_untouched(self):
        now = timezone.now()
        report = self._create_report(
            "SCM-2026-RECENT",
            scan_status=ScanStatus.PENDING,
            scan_attempts=1,
            scan_dispatched_at=now - timedelta(minutes=2),
        )

        with patch("apps.scanner.jobs.dispatch_scan") as mock_dispatch:
            res = redispatch_pending_scans()
            assert res.get("redispatched", 0) == 0
            assert mock_dispatch.call_count == 0

        report.refresh_from_db()
        assert report.scan_attempts == 1
        assert report.scan_status == ScanStatus.PENDING

    def test_stalled_pending_dispatched_over_5_min_redispatches(self):
        now = timezone.now()
        report = self._create_report(
            "SCM-2026-STALLED",
            scan_status=ScanStatus.PENDING,
            scan_attempts=2,
            scan_dispatched_at=now - timedelta(minutes=6),
        )

        with patch("apps.scanner.jobs.dispatch_scan") as mock_dispatch:
            res = redispatch_pending_scans()
            assert res.get("redispatched", 0) >= 1
            mock_dispatch.assert_called_once_with(report.id)

    def test_pending_never_dispatched_redispatches(self):
        report = self._create_report(
            "SCM-2026-NEVERDISPATCH",
            scan_status=ScanStatus.PENDING,
            scan_attempts=0,
            scan_dispatched_at=None,
        )

        with patch("apps.scanner.jobs.dispatch_scan") as mock_dispatch:
            res = redispatch_pending_scans()
            assert res.get("redispatched", 0) >= 1
            mock_dispatch.assert_called_once_with(report.id)

    def test_stalled_pending_attempts_gte_5_transitions_to_failed(self):
        now = timezone.now()
        report = self._create_report(
            "SCM-2026-MAXATTEMPTS",
            scan_status=ScanStatus.PENDING,
            scan_attempts=5,
            scan_dispatched_at=now - timedelta(minutes=10),
        )

        with patch("apps.scanner.jobs.dispatch_scan") as mock_dispatch, patch("apps.scanner.jobs.metrics.emit") as mock_metrics:
            res = redispatch_pending_scans()
            assert res.get("failed", 0) >= 1
            # Must NOT call dispatch_scan
            assert mock_dispatch.call_count == 0

        report.refresh_from_db()
        assert report.scan_status == ScanStatus.FAILED

        # Check audit log
        audit = SystemAuditLog.objects.filter(
            event_type=AuditEventType.SCAN_FAILED,
            target_type="REPORT",
            target_id=str(report.id),
        ).first()
        assert audit is not None
        assert audit.severity == AuditSeverity.WARN
        assert audit.metadata.get("scan_attempts") == 5

        # Check metric
        mock_metrics.assert_any_call("ScansFailed", 1)

    def test_to_be_proven_11_advisory_locked_retry_convergence(self):
        """
        Prove TO BE PROVEN #11: Advisory-Locked Retry Convergence.
        Holding pg_advisory_lock on another DB connection causes run_jobs
        to skip execution cleanly; releasing the lock allows it to process.
        """
        now = timezone.now()
        report = self._create_report(
            "SCM-2026-LOCKTEST",
            scan_status=ScanStatus.PENDING,
            scan_attempts=1,
            scan_dispatched_at=now - timedelta(minutes=10),
        )

        lock_id = get_lock_id_for_job("redispatch_pending_scans")
        other_conn = connections.create_connection("default")
        try:
            with other_conn.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s);", [lock_id])
                acquired = cursor.fetchone()[0]
                assert acquired is True, "Failed to acquire advisory lock on separate connection"

                try:
                    out = StringIO()
                    call_command("run_jobs", job="redispatch_pending_scans", stdout=out)
                    output = out.getvalue()
                    assert "locked" in output.lower() or "skipped" in output.lower()

                    # Report must not have been processed
                    report.refresh_from_db()
                    assert report.scan_attempts == 1
                finally:
                    cursor.execute("SELECT pg_advisory_unlock(%s);", [lock_id])
        finally:
            other_conn.close()

        # After releasing lock, run_jobs processes the stalled report
        with patch("apps.scanner.jobs.dispatch_scan") as mock_dispatch:
            out_after = StringIO()
            call_command("run_jobs", job="redispatch_pending_scans", stdout=out_after)
            mock_dispatch.assert_called_once_with(report.id)
            output_after = out_after.getvalue()
            assert "completed" in output_after.lower() or "success" in output_after.lower()
