import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.models import IndicatorStatus, IndicatorType, ScamCategory, ThreatLevel, VerifiedIndicator
from apps.intel.selectors.intel_selectors import count_pending_by_indicator, find_active_indicators
from apps.reports.models import Platform, ReportIndicator, ReportStatus, ScamReport


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_sel@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


def create_verified_indicator(
    analyst,
    itype: str,
    norm_val: str,
    status: str = IndicatorStatus.ACTIVE,
    threat_level: str = ThreatLevel.MEDIUM,
) -> VerifiedIndicator:
    now = timezone.now()
    return VerifiedIndicator.objects.create(
        id=uuid.uuid4(),
        type=itype,
        normalized_value=norm_val,
        display_value=norm_val,
        primary_category=ScamCategory.PHISHING,
        threat_level=threat_level,
        total_report_count=1,
        first_seen_at=now,
        last_seen_at=now,
        status=status,
        public_note="Test note",
        verified_by=analyst,
        verified_at=now,
    )


def create_report_with_indicators(
    ref: str,
    status: str = ReportStatus.PENDING,
    indicators: list[tuple[str, str]] | None = None,
) -> ScamReport:
    report = ScamReport.objects.create(
        reference_code=ref,
        category=ScamCategory.PHISHING,
        platform=Platform.WHATSAPP,
        financial_loss=Decimal("100.00"),
        currency="MYR",
        incident_date=timezone.now().date(),
        message_text="Scam message text",
        status=status,
    )
    for itype, val in (indicators or []):
        ReportIndicator.objects.create(
            report=report,
            type=itype,
            raw_value=val,
            normalized_value=val,
            display_value=val,
        )
    return report


@pytest.mark.django_db
class TestFindActiveIndicators:
    def test_empty_pairs_returns_none_zero_queries(self, django_assert_num_queries):
        with django_assert_num_queries(0):
            qs = find_active_indicators([])
            assert list(qs) == []

    def test_finds_active_indicators_matching_pairs(self, analyst_user):
        vi1 = create_verified_indicator(analyst_user, IndicatorType.PHONE, "+60123456789", status=IndicatorStatus.ACTIVE)
        vi2 = create_verified_indicator(analyst_user, IndicatorType.URL, "https://phish.com", status=IndicatorStatus.ACTIVE)
        # Inactive / revoked indicator
        create_verified_indicator(analyst_user, IndicatorType.EMAIL, "scam@test.com", status=IndicatorStatus.REVOKED)
        # Different value
        create_verified_indicator(analyst_user, IndicatorType.PHONE, "+60199999999", status=IndicatorStatus.ACTIVE)

        pairs = [
            (IndicatorType.PHONE, "+60123456789"),
            (IndicatorType.URL, "https://phish.com"),
            (IndicatorType.EMAIL, "scam@test.com"),  # REVOKED, must be excluded
            (IndicatorType.PHONE, "+60100000000"),  # Does not exist
        ]

        result = list(find_active_indicators(pairs))
        assert len(result) == 2
        result_ids = {r.id for r in result}
        assert result_ids == {vi1.id, vi2.id}


@pytest.mark.django_db
class TestCountPendingByIndicator:
    def test_empty_pairs_returns_empty_dict_zero_queries(self, django_assert_num_queries):
        with django_assert_num_queries(0):
            counts = count_pending_by_indicator([])
            assert counts == {}

    def test_counts_distinct_pending_reports_in_single_query(self, django_assert_num_queries):
        p1 = (IndicatorType.PHONE, "+60111111111")
        p2 = (IndicatorType.URL, "https://fakebank.com")
        p3 = (IndicatorType.EMAIL, "nobody@scam.com")

        # Report 1 (PENDING) has p1 and p2
        create_report_with_indicators("SCM-2026-PND00001", ReportStatus.PENDING, [p1, p2])
        # Report 2 (PENDING) has p1
        create_report_with_indicators("SCM-2026-PND00002", ReportStatus.PENDING, [p1])
        # Report 3 (VERIFIED) has p1 -> should NOT be counted
        create_report_with_indicators("SCM-2026-PND00003", ReportStatus.VERIFIED, [p1])
        # Report 4 (REJECTED) has p2 -> should NOT be counted
        create_report_with_indicators("SCM-2026-PND00004", ReportStatus.REJECTED, [p2])

        # Exactly 1 query executed
        with django_assert_num_queries(1):
            counts = count_pending_by_indicator([p1, p2, p3])

        assert counts[p1] == 2
        assert counts[p2] == 1
        assert counts[p3] == 0
