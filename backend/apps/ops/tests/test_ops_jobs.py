from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.audit import log_event
from apps.ops.jobs import aggregate_ops_metrics
from apps.ops.models import AuditEventType, AuditSeverity
from apps.reports.models import ScamCategory, ScamReport
from apps.reports.tests.factories import ScamReportFactory


@pytest.mark.django_db
class TestOpsJobs:
    def test_aggregate_ops_metrics_counts_and_pushes_metrics(self):
        """Job computes recent counts from DB and pushes them via put_metrics."""
        now = timezone.now()

        # 1. Recent scam reports
        ScamReportFactory(
            category=ScamCategory.PHISHING.value,
            is_high_priority=True,
        )
        ScamReportFactory(
            category=ScamCategory.IMPERSONATION.value,
            is_high_priority=False,
        )

        # 2. Old scam report outside the 1h window (should not be counted)
        old_report = ScamReportFactory(
            category=ScamCategory.FAKE_JOB.value,
            is_high_priority=True,
        )
        ScamReport.objects.filter(id=old_report.id).update(created_at=now - timedelta(hours=2))

        # 3. Recent audit logs
        log_event(
            event_type=AuditEventType.RATE_LIMIT_BLOCK.value,
            severity=AuditSeverity.WARN.value,
            metadata={"reason": "test"},
        )
        log_event(
            event_type=AuditEventType.LOGIN_FAILURE.value,
            severity=AuditSeverity.WARN.value,
            metadata={"reason": "bad_password"},
        )
        log_event(
            event_type=AuditEventType.ADVISORY_PUBLISHED.value,
            severity=AuditSeverity.INFO.value,
            metadata={"title": "Test Advisory"},
        )

        with patch("apps.ops.jobs.put_metrics") as mock_put_metrics:
            mock_put_metrics.return_value = True
            result = aggregate_ops_metrics()

            assert "Aggregated metrics pushed" in result
            assert mock_put_metrics.called
            metric_data = mock_put_metrics.call_args[0][0]

            metrics_by_name = {m["name"]: m["value"] for m in metric_data}
            assert metrics_by_name["ReportsSubmitted"] == 2.0
            assert metrics_by_name["ReportsHighPriority"] == 1.0
            assert metrics_by_name["RateLimitBlocks"] >= 1.0
            assert metrics_by_name["LoginFailures"] >= 1.0
            assert metrics_by_name["AlertsPublished"] >= 1.0

    def test_run_jobs_command_executes_aggregate_ops_metrics(self):
        """run_jobs management command executes aggregate_ops_metrics under advisory lock."""
        out = StringIO()
        call_command("run_jobs", job="aggregate_ops_metrics", stdout=out)
        output = out.getvalue()
        assert "Job 'aggregate_ops_metrics' completed" in output
