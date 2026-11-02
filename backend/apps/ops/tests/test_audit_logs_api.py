from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.audit import log_event
from apps.ops.models import AuditEventType, AuditSeverity


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="audit_admin@scamshield.test",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="audit_analyst@scamshield.test",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestAuditLogsApi:
    def test_anonymous_and_non_admin_rejected(self, analyst_user):
        client = APIClient()
        # Anonymous -> 401
        res = client.get("/api/v1/admin-portal/audit-logs/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # Non-admin -> 403
        client.force_authenticate(user=analyst_user)
        res = client.get("/api/v1/admin-portal/audit-logs/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_list_audit_logs_pagination_and_fields(self, admin_user):
        for i in range(5):
            log_event(
                event_type=AuditEventType.REPORT_SUBMITTED.value,
                actor=admin_user,
                severity=AuditSeverity.INFO.value,
                metadata={"index": i},
            )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        res = client.get("/api/v1/admin-portal/audit-logs/")

        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert "count" in data
        assert "results" in data
        assert len(data["results"]) >= 5

        first = data["results"][0]
        assert "id" in first
        assert "occurred_at" in first
        assert "event_type" in first
        assert "severity" in first
        assert "actor_id" in first
        assert "actor_role" in first
        assert first["actor_role"] == Role.ADMIN.value
        assert "metadata" in first

    def test_filtering_by_event_type_and_severity(self, admin_user):
        log_event(
            event_type=AuditEventType.LOGIN_FAILURE.value,
            severity=AuditSeverity.WARN.value,
            metadata={"user": "attacker"},
        )
        log_event(
            event_type=AuditEventType.RATE_LIMIT_BLOCK.value,
            severity=AuditSeverity.ALERT.value,
            metadata={"user": "spammer"},
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)

        res_type = client.get(f"/api/v1/admin-portal/audit-logs/?event_type={AuditEventType.LOGIN_FAILURE.value}")
        assert res_type.status_code == status.HTTP_200_OK
        for r in res_type.json()["results"]:
            assert r["event_type"] == AuditEventType.LOGIN_FAILURE.value

        res_sev = client.get(f"/api/v1/admin-portal/audit-logs/?severity={AuditSeverity.ALERT.value}")
        assert res_sev.status_code == status.HTTP_200_OK
        for r in res_sev.json()["results"]:
            assert r["severity"] == AuditSeverity.ALERT.value

    def test_filtering_by_date_range(self, admin_user):
        now = timezone.now()
        client = APIClient()
        client.force_authenticate(user=admin_user)

        date_from = (now - timedelta(days=1)).isoformat()
        date_to = (now + timedelta(days=1)).isoformat()

        res = client.get(f"/api/v1/admin-portal/audit-logs/?date_from={date_from}&date_to={date_to}")
        assert res.status_code == status.HTTP_200_OK

        # Inverted date range fails with 400
        res_invalid = client.get(f"/api/v1/admin-portal/audit-logs/?date_from={date_to}&date_to={date_from}")
        assert res_invalid.status_code == status.HTTP_400_BAD_REQUEST

    def test_filtering_by_actor_id(self, admin_user):
        target_user = User.objects.create_user(
            email="target_actor@scamshield.test",
            password="ValidPassword123!",
            role=Role.CITIZEN,
        )
        log_event(
            event_type=AuditEventType.USER_REGISTERED.value,
            actor=target_user,
            severity=AuditSeverity.INFO.value,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)

        res = client.get(f"/api/v1/admin-portal/audit-logs/?actor_id={target_user.id}")
        assert res.status_code == status.HTTP_200_OK
        assert len(res.json()["results"]) >= 1
        assert res.json()["results"][0]["actor_id"] == str(target_user.id)

        # Invalid UUID -> 400
        res_bad = client.get("/api/v1/admin-portal/audit-logs/?actor_id=invalid-uuid")
        assert res_bad.status_code == status.HTTP_400_BAD_REQUEST

    def test_filtering_by_ip_hash_minimum_length(self, admin_user):
        ip_hash = "11223344556677889900aabbccddeeff"
        log_event(
            event_type=AuditEventType.LOGIN_SUCCESS.value,
            ip_hash=ip_hash,
            severity=AuditSeverity.INFO.value,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)

        # Prefix >= 8 chars succeeds
        res = client.get("/api/v1/admin-portal/audit-logs/?ip_hash=11223344")
        assert res.status_code == status.HTTP_200_OK
        assert len(res.json()["results"]) >= 1

        # Prefix < 8 chars returns 400 validation error
        res_short = client.get("/api/v1/admin-portal/audit-logs/?ip_hash=112233")
        assert res_short.status_code == status.HTTP_400_BAD_REQUEST
        assert "ip_hash" in str(res_short.json())

    def test_query_count_bounded(self, admin_user):
        """Audit log list query executes <= 3 queries (COUNT + SELECT with select_related)."""
        for i in range(15):
            log_event(
                event_type=AuditEventType.REPORT_SUBMITTED.value,
                actor=admin_user,
                severity=AuditSeverity.INFO.value,
                metadata={"i": i},
            )

        client = APIClient()
        client.force_authenticate(user=admin_user)

        with CaptureQueriesContext(connection) as ctx:
            res = client.get("/api/v1/admin-portal/audit-logs/?page_size=10")

        assert res.status_code == status.HTTP_200_OK
        assert len(ctx) <= 3, f"Expected <= 3 queries, got {len(ctx)}: {[q['sql'] for q in ctx]}"

    def test_csv_export_streaming_and_sanitization(self, admin_user):
        """CSV export returns streaming CSV with no PII and neutralizes formula injection."""
        log_event(
            event_type=AuditEventType.LOGIN_FAILURE.value,
            actor=admin_user,
            severity=AuditSeverity.WARN.value,
            target=("=HYPERLINK", "http://evil.com"),
            metadata={"safe": "val"},
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)

        res = client.get("/api/v1/admin-portal/audit-logs/export/")
        assert res.status_code == status.HTTP_200_OK
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="audit_logs.csv"' in res["Content-Disposition"]

        content = b"".join(res.streaming_content).decode("utf-8")
        lines = content.strip().split("\r\n") if "\r\n" in content else content.strip().split("\n")

        assert len(lines) >= 2
        header = lines[0]
        assert "id,occurred_at,event_type,severity,actor_id" in header

        # Verify formula injection neutralization on target_type: '=HYPERLINK' prefixed with "'"
        assert "'=HYPERLINK" in content
