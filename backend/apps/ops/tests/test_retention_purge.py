from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.audit import log_event
from apps.ops.jobs import purge_expired_audit_logs
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog


@pytest.mark.django_db
class TestRetentionPurge:
    def test_purge_expired_audit_logs_respects_retention_windows(self):
        """
        INFO logs older than 90 days are purged; younger than 90 days are preserved.
        Security logs (WARN/ALERT/security event) older than 365 days are purged;
        younger than 365 days are preserved.
        """
        now = timezone.now()

        # 1. INFO log at 91 days old -> PURGED
        l1 = log_event(
            event_type=AuditEventType.REPORT_SUBMITTED.value,
            severity=AuditSeverity.INFO.value,
            metadata={"item": "info_old"},
        )
        # 2. INFO log at 89 days old -> PRESERVED
        l2 = log_event(
            event_type=AuditEventType.REPORT_SUBMITTED.value,
            severity=AuditSeverity.INFO.value,
            metadata={"item": "info_recent"},
        )

        # 3. WARN security log at 366 days old -> PURGED
        l3 = log_event(
            event_type=AuditEventType.RATE_LIMIT_BLOCK.value,
            severity=AuditSeverity.WARN.value,
            metadata={"item": "warn_old"},
        )
        # 4. WARN security log at 364 days old -> PRESERVED (even though > 90d)
        l4 = log_event(
            event_type=AuditEventType.RATE_LIMIT_BLOCK.value,
            severity=AuditSeverity.WARN.value,
            metadata={"item": "warn_mid"},
        )
        # 5. ALERT security log at 366 days old -> PURGED
        l5 = log_event(
            event_type=AuditEventType.LOGIN_FAILURE.value,
            severity=AuditSeverity.ALERT.value,
            metadata={"item": "alert_old"},
        )
        # 6. ALERT security log at 100 days old -> PRESERVED (even though > 90d)
        l6 = log_event(
            event_type=AuditEventType.LOGIN_FAILURE.value,
            severity=AuditSeverity.ALERT.value,
            metadata={"item": "alert_mid"},
        )

        # Update timestamps with authorized session context to backdate test rows
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL scamshield.audit_purge_allowed = 'on';")
            cursor.execute(
                "UPDATE ops_systemauditlog SET occurred_at = %s WHERE id = %s",
                [now - timedelta(days=91), l1.id],
            )
            cursor.execute(
                "UPDATE ops_systemauditlog SET occurred_at = %s WHERE id = %s",
                [now - timedelta(days=89), l2.id],
            )
            cursor.execute(
                "UPDATE ops_systemauditlog SET occurred_at = %s WHERE id = %s",
                [now - timedelta(days=366), l3.id],
            )
            cursor.execute(
                "UPDATE ops_systemauditlog SET occurred_at = %s WHERE id = %s",
                [now - timedelta(days=364), l4.id],
            )
            cursor.execute(
                "UPDATE ops_systemauditlog SET occurred_at = %s WHERE id = %s",
                [now - timedelta(days=366), l5.id],
            )
            cursor.execute(
                "UPDATE ops_systemauditlog SET occurred_at = %s WHERE id = %s",
                [now - timedelta(days=100), l6.id],
            )

        purged_count = purge_expired_audit_logs()
        # Should have purged l1, l3, l5 = 3 rows
        assert purged_count >= 3

        remaining_ids = set(SystemAuditLog.objects.values_list("id", flat=True))
        assert l1.id not in remaining_ids
        assert l2.id in remaining_ids
        assert l3.id not in remaining_ids
        assert l4.id in remaining_ids
        assert l5.id not in remaining_ids
        assert l6.id in remaining_ids

    def test_run_jobs_purge_expired_audit_logs(self):
        """run_jobs executes purge_expired_audit_logs cleanly under advisory lock."""
        out = StringIO()
        call_command("run_jobs", job="purge_expired_audit_logs", stdout=out)
        assert "Job 'purge_expired_audit_logs' completed" in out.getvalue()
