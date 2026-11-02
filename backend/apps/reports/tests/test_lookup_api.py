from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.models import (
    IndicatorStatus,
    IndicatorType,
    ScamCategory,
    ThreatLevel,
    VerifiedIndicator,
)
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.reports.models import ReportIndicator, ReportStatus, ScamReport


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_api@example.com",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestLookupAPI:
    def setup_method(self):
        cache.clear()

    def test_public_access_no_auth_required(self, api_client):
        res = api_client.post("/api/v1/lookups/", {"query": "innocent-site.org"}, format="json")
        assert res.status_code == 200
        assert res.data["verdict"] == "GREEN"

    def test_missing_or_blank_query_returns_400(self, api_client):
        res_empty = api_client.post("/api/v1/lookups/", {}, format="json")
        assert res_empty.status_code == 400
        assert res_empty.data["error"]["code"] == "validation_error"

        res_blank = api_client.post("/api/v1/lookups/", {"query": "   "}, format="json")
        assert res_blank.status_code == 400
        assert res_blank.data["error"]["code"] == "validation_error"

    def test_red_verdict_response_contract(self, api_client, analyst_user):
        now = timezone.now()
        VerifiedIndicator.objects.create(
            type=IndicatorType.PHONE,
            normalized_value="+60123456789",
            display_value="+601•••••6789",
            primary_category=ScamCategory.ECOMMERCE_FRAUD,
            threat_level=ThreatLevel.HIGH,
            total_report_count=7,
            first_seen_at=now - timedelta(days=10),
            last_seen_at=now,
            status=IndicatorStatus.ACTIVE,
            public_note="Verified impersonation and fraud.",
            verified_by=analyst_user,
            verified_at=now,
        )

        res = api_client.post("/api/v1/lookups/", {"query": "012-3456789"}, format="json")
        assert res.status_code == 200
        data = res.data
        assert data["verdict"] == "RED"
        assert data["threat_level"] == ThreatLevel.HIGH
        assert data["category"] == ScamCategory.ECOMMERCE_FRAUD
        assert data["report_count"] == 7
        assert data["public_note"] == "Verified impersonation and fraud."
        assert "verified scam" in data["message"].lower()

    def test_yellow_verdict_response_contract(self, api_client):
        report = ScamReport.objects.create(
            reference_code="SCAM-2026-YEL1",
            category=ScamCategory.PHISHING,
            platform="SMS",
            status=ReportStatus.PENDING,
            message_text="Got a fake bank login link.",
            currency="MYR",
            country_code="MY",
        )
        ReportIndicator.objects.create(
            report=report,
            type=IndicatorType.URL,
            raw_value="https://suspicious-link.xyz/login",
            normalized_value="suspicious-link.xyz/login",
            display_value="susp••••.xyz/login",
        )

        res = api_client.post(
            "/api/v1/lookups/",
            {"query": "https://suspicious-link.xyz/login"},
            format="json",
        )
        assert res.status_code == 200
        data = res.data
        assert data["verdict"] == "YELLOW"
        assert data["report_count"] == 1
        assert data["threat_level"] is None
        assert "awaiting verification" in data["message"].lower()

    def test_privacy_snapshot_never_leaks_pii(self, api_client):
        """R-C5, R-C8: Public responses never include victim text, raw indicators, reporter, IP, evidence."""
        secret_narrative = "I lost $5000 to John Doe at 192.168.1.1, phone 012-9999888"
        report = ScamReport.objects.create(
            reference_code="SCAM-CONFIDENTIAL-999",
            category=ScamCategory.IMPERSONATION,
            platform="TELEGRAM",
            status=ReportStatus.PENDING,
            message_text=secret_narrative,
            currency="MYR",
            country_code="MY",
        )
        ReportIndicator.objects.create(
            report=report,
            type=IndicatorType.PHONE,
            raw_value="012-9999888",
            normalized_value="+60129999888",
            display_value="+601•••••9888",
        )

        res = api_client.post("/api/v1/lookups/", {"query": "012-9999888"}, format="json")
        assert res.status_code == 200
        res_str = str(res.data)

        # Strictly assert NO PII, NO internal references, NO report IDs leaked
        assert "SCAM-CONFIDENTIAL-999" not in res_str
        assert str(report.id) not in res_str
        assert secret_narrative not in res_str
        assert "192.168.1.1" not in res_str

    def test_lookup_rate_limiting_throttle(self, api_client, monkeypatch):
        mock_emitted = []
        monkeypatch.setattr("apps.core.metrics.emit", lambda name, val=1: mock_emitted.append((name, val)))

        # Send 30 requests - all succeed
        for i in range(30):
            res = api_client.post(
                "/api/v1/lookups/",
                {"query": f"clean-domain-{i}.com"},
                format="json",
                REMOTE_ADDR="198.51.100.42",
            )
            assert res.status_code == 200

        # 31st request should be throttled
        res_blocked = api_client.post(
            "/api/v1/lookups/",
            {"query": "clean-domain-31.com"},
            format="json",
            REMOTE_ADDR="198.51.100.42",
        )
        assert res_blocked.status_code == 429
        assert res_blocked.data["error"]["code"] == "throttled"
        assert "Retry-After" in res_blocked.headers

        # Assert RATE_LIMIT_BLOCK audit row
        audit_row = SystemAuditLog.objects.filter(
            event_type=AuditEventType.RATE_LIMIT_BLOCK,
            metadata__action="lookup",
        ).first()
        assert audit_row is not None
        assert audit_row.metadata["threshold"] == 30

        # Assert RateLimitBlocks metric emitted
        assert ("RateLimitBlocks", 1) in mock_emitted
