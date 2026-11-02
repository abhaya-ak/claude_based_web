from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound, Throttled

from apps.accounts.models import Role, User
from apps.core import audit
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.reports.models import Platform, ScamCategory, ScamReport
from apps.reports.services.report_service import track_report
from apps.reports.throttling import (
    check_report_submission_throttle,
    check_report_tracking_throttle,
)


@pytest.mark.django_db
class TestReportSubmissionThrottling:
    def test_anonymous_rate_limit_boundary(self):
        ip_hash = "anon_test_ip_hash_12345"

        # Create 4 past REPORT_SUBMITTED audit events within the last hour
        for _ in range(4):
            audit.log_event(
                event_type=AuditEventType.REPORT_SUBMITTED,
                ip_hash=ip_hash,
                metadata={"category": "PHISHING", "file_count": 0},
            )

        # 5th check should pass
        check_report_submission_throttle(ip_hash=ip_hash, user=None)

        # Log the 5th event
        audit.log_event(
            event_type=AuditEventType.REPORT_SUBMITTED,
            ip_hash=ip_hash,
            metadata={"category": "PHISHING", "file_count": 0},
        )

        # 6th check should raise Throttled
        with pytest.raises(Throttled) as exc:
            check_report_submission_throttle(ip_hash=ip_hash, user=None)
        assert exc.value.wait == 3600

        # Verify RATE_LIMIT_BLOCK was logged
        block_log = SystemAuditLog.objects.filter(
            event_type=AuditEventType.RATE_LIMIT_BLOCK,
            actor_ip_hash=ip_hash,
        ).first()
        assert block_log is not None
        assert block_log.metadata["action"] == "report_submission"
        assert block_log.metadata["threshold"] == 5

    def test_authenticated_rate_limit_boundary(self):
        user = User.objects.create_user(
            email="auth_throttle@example.com",
            password="StrongPassword123!",
            role=Role.CITIZEN,
        )
        ip_hash = "auth_test_ip_hash_67890"

        # Create 19 past REPORT_SUBMITTED events for this user within the last hour
        for _ in range(19):
            audit.log_event(
                event_type=AuditEventType.REPORT_SUBMITTED,
                actor=user,
                ip_hash=ip_hash,
                metadata={"category": "PHISHING", "file_count": 0},
            )

        # 20th check should pass
        check_report_submission_throttle(ip_hash=ip_hash, user=user)

        # Log the 20th event
        audit.log_event(
            event_type=AuditEventType.REPORT_SUBMITTED,
            actor=user,
            ip_hash=ip_hash,
            metadata={"category": "PHISHING", "file_count": 0},
        )

        # 21st check should raise Throttled
        with pytest.raises(Throttled) as exc:
            check_report_submission_throttle(ip_hash=ip_hash, user=user)
        assert exc.value.wait == 3600

        # Verify RATE_LIMIT_BLOCK was logged with target user
        block_log = SystemAuditLog.objects.filter(
            event_type=AuditEventType.RATE_LIMIT_BLOCK,
            actor=user,
        ).first()
        assert block_log is not None
        assert block_log.metadata["threshold"] == 20

    def test_expired_audit_events_do_not_count_toward_throttle(self):
        ip_hash = "expired_throttle_ip"
        two_hours_ago = timezone.now() - timedelta(hours=2)

        # Create 10 events from 2 hours ago
        for _ in range(10):
            log = audit.log_event(
                event_type=AuditEventType.REPORT_SUBMITTED,
                ip_hash=ip_hash,
                metadata={"category": "PHISHING", "file_count": 0},
            )
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SET scamshield.audit_purge_allowed = 'on';")
                try:
                    SystemAuditLog.objects.filter(id=log.id).update(occurred_at=two_hours_ago)
                finally:
                    cursor.execute("SET scamshield.audit_purge_allowed = 'off';")

        # Should pass because all events are expired
        check_report_submission_throttle(ip_hash=ip_hash, user=None)

    def test_authenticated_reports_do_not_count_toward_anonymous_throttle(self):
        user = User.objects.create_user(
            email="auth_ip_overlap@example.com",
            password="StrongPassword123!",
            role=Role.CITIZEN,
        )
        ip_hash = "shared_ip_hash_112233"

        # User submits 5 reports from this IP
        for _ in range(5):
            audit.log_event(
                event_type=AuditEventType.REPORT_SUBMITTED,
                actor=user,
                ip_hash=ip_hash,
                metadata={"category": "PHISHING", "file_count": 0},
            )

        # Anonymous submission from same IP must NOT be throttled by user's reports
        check_report_submission_throttle(ip_hash=ip_hash, user=None)



@pytest.mark.django_db
class TestReportTrackingThrottling:
    def test_tracking_failure_throttle_boundary(self):
        ip_hash = "track_fail_ip_9999"

        # 9 past failures
        for _ in range(9):
            audit.log_event(
                event_type=AuditEventType.REPORT_TRACK_FAILED,
                ip_hash=ip_hash,
                metadata={"ref_code": "SCM-2026-TESTCODE"},
            )

        # 10th check passes
        check_report_tracking_throttle(ip_hash=ip_hash)

        # 10th failure logged
        audit.log_event(
            event_type=AuditEventType.REPORT_TRACK_FAILED,
            ip_hash=ip_hash,
            metadata={"ref_code": "SCM-2026-TESTCODE"},
        )

        # 11th check raises Throttled
        with pytest.raises(Throttled) as exc:
            check_report_tracking_throttle(ip_hash=ip_hash)
        assert exc.value.wait == 900

        # Verify RATE_LIMIT_BLOCK logged
        block = SystemAuditLog.objects.filter(
            event_type=AuditEventType.RATE_LIMIT_BLOCK,
            actor_ip_hash=ip_hash,
        ).first()
        assert block is not None
        assert block.metadata["action"] == "report_tracking"
        assert block.metadata["threshold"] == 10

    def test_tracking_identical_404_for_unknown_reference_and_wrong_key(self):
        ip_hash = "track_enum_ip"
        # 1. Non-existent reference code
        with pytest.raises(NotFound) as exc1:
            track_report(
                reference_code="SCM-2026-NONEXIST",
                access_key="wrong_key_12345678901234567890",
                ip_hash=ip_hash,
            )
        assert exc1.value.detail == "Report not found."

        # 2. Existing report with wrong access key
        report = ScamReport.objects.create(
            reference_code="SCM-2026-EXIST001",
            is_anonymous=True,
            access_key_hash="valid_hash_placeholder_1234567890123456789012345678901234567890",
            category=ScamCategory.PHISHING,
            platform=Platform.SMS,
            message_text="Scam message",
            currency="MYR",
            country_code="MY",
        )

        with pytest.raises(NotFound) as exc2:
            track_report(
                reference_code=report.reference_code,
                access_key="wrong_key_12345678901234567890",
                ip_hash=ip_hash,
            )
        assert exc2.value.detail == "Report not found."
        # Both must have identical exception class and detail string
        assert str(exc1.value.detail) == str(exc2.value.detail)
