from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.models import (
    IndicatorStatus,
    IndicatorType,
    ScamCategory,
    ThreatLevel,
    VerifiedIndicator,
)
from apps.reports.models import ReportIndicator, ReportStatus, ScamReport
from apps.reports.services.lookup_service import determine_verdict


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_lookup@example.com",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestLookupService:
    def test_active_verified_indicator_returns_red(self, analyst_user):
        now = timezone.now()
        VerifiedIndicator.objects.create(
            type=IndicatorType.PHONE,
            normalized_value="+60123456789",
            display_value="+601•••••6789",
            primary_category=ScamCategory.ECOMMERCE_FRAUD,
            threat_level=ThreatLevel.HIGH,
            total_report_count=5,
            first_seen_at=now - timedelta(days=10),
            last_seen_at=now,
            status=IndicatorStatus.ACTIVE,
            public_note="Known e-commerce scam contact.",
            verified_by=analyst_user,
            verified_at=now,
        )

        result = determine_verdict("012-3456789")
        assert result["verdict"] == "RED"
        assert result["threat_level"] == ThreatLevel.HIGH
        assert result["category"] == ScamCategory.ECOMMERCE_FRAUD
        assert result["report_count"] == 5
        assert result["public_note"] == "Known e-commerce scam contact."
        assert "verified scam" in result["message"].lower()

    def test_highest_threat_level_wins_when_multiple_matches(self, analyst_user):
        now = timezone.now()
        # Create MEDIUM for URL and CRITICAL for DOMAIN
        VerifiedIndicator.objects.create(
            type=IndicatorType.URL,
            normalized_value="login.evil-phish.xyz/secure/login.php?ref=123",
            display_value="login.••••.xyz/secure/login.php?ref=123",
            primary_category=ScamCategory.PHISHING,
            threat_level=ThreatLevel.MEDIUM,
            total_report_count=2,
            first_seen_at=now - timedelta(days=2),
            last_seen_at=now,
            status=IndicatorStatus.ACTIVE,
            verified_by=analyst_user,
            verified_at=now,
        )
        VerifiedIndicator.objects.create(
            type=IndicatorType.DOMAIN,
            normalized_value="evil-phish.xyz",
            display_value="evil••••.xyz",
            primary_category=ScamCategory.PHISHING,
            threat_level=ThreatLevel.CRITICAL,
            total_report_count=15,
            first_seen_at=now - timedelta(days=30),
            last_seen_at=now,
            status=IndicatorStatus.ACTIVE,
            verified_by=analyst_user,
            verified_at=now,
        )

        result = determine_verdict("https://login.evil-phish.xyz/secure/login.php?ref=123")
        assert result["verdict"] == "RED"
        assert result["threat_level"] == ThreatLevel.CRITICAL

    def test_domain_blacklist_inheritance_returns_red(self, analyst_user):
        """TO BE PROVEN #13: URL inherits RED verdict from its registered domain blacklist entry."""
        now = timezone.now()
        VerifiedIndicator.objects.create(
            type=IndicatorType.DOMAIN,
            normalized_value="bad-actor-bank.com",
            display_value="bad-••••.com",
            primary_category=ScamCategory.PHISHING,
            threat_level=ThreatLevel.HIGH,
            total_report_count=8,
            first_seen_at=now - timedelta(days=5),
            last_seen_at=now,
            status=IndicatorStatus.ACTIVE,
            verified_by=analyst_user,
            verified_at=now,
        )

        # Lookup with a deep URL on that domain
        result = determine_verdict("https://bad-actor-bank.com/malicious/portal.html?token=abc")
        assert result["verdict"] == "RED"
        assert result["threat_level"] == ThreatLevel.HIGH
        assert result["report_count"] == 8

    def test_revoked_indicator_returns_not_red(self, analyst_user):
        now = timezone.now()
        VerifiedIndicator.objects.create(
            type=IndicatorType.DOMAIN,
            normalized_value="cleared-business.org",
            display_value="clea••••.org",
            primary_category=ScamCategory.OTHER,
            threat_level=ThreatLevel.MEDIUM,
            total_report_count=1,
            first_seen_at=now - timedelta(days=5),
            last_seen_at=now,
            status=IndicatorStatus.REVOKED,
            verified_by=analyst_user,
            verified_at=now,
            revoked_by=analyst_user,
            revoke_reason="False positive",
        )

        result = determine_verdict("cleared-business.org")
        assert result["verdict"] != "RED"
        assert result["verdict"] == "GREEN"

    def test_pending_reports_returns_yellow(self):
        report = ScamReport.objects.create(
            reference_code="SCAM-2026-TEST1",
            category=ScamCategory.FAKE_JOB,
            platform="WHATSAPP",
            status=ReportStatus.PENDING,
            message_text="Offered fake high paying job.",
            currency="MYR",
            country_code="MY",
        )
        ReportIndicator.objects.create(
            report=report,
            type=IndicatorType.PHONE,
            raw_value="012-3456789",
            normalized_value="+60123456789",
            display_value="+601•••••6789",
        )

        result = determine_verdict("012-3456789")
        assert result["verdict"] == "YELLOW"
        assert result["report_count"] == 1
        assert "awaiting verification" in result["message"].lower()

    def test_clean_indicator_returns_green(self):
        result = determine_verdict("innocent-domain-example.com")
        assert result["verdict"] == "GREEN"
        assert result["report_count"] == 0
        assert "no scam reports found" in result["message"].lower()

    def test_conversational_text_returns_green(self):
        result = determine_verdict("Is this job offer real please check")
        assert result["verdict"] == "GREEN"
        assert result["report_count"] == 0
