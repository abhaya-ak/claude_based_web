import time

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.models import IndicatorStatus, IndicatorType, ScamCategory, ThreatLevel, VerifiedIndicator
from apps.reports.models import ReportIndicator, ReportStatus, ScamReport


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_lookup_q@example.com",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestLookupQueryBoundsAndLatency:
    def test_lookup_query_count_for_active_indicator(self, api_client, analyst_user, django_assert_max_num_queries):
        now = timezone.now()
        VerifiedIndicator.objects.create(
            type=IndicatorType.DOMAIN,
            normalized_value="fraud-site-test.com",
            display_value="fraud••••.com",
            primary_category=ScamCategory.PHISHING,
            threat_level=ThreatLevel.HIGH,
            total_report_count=10,
            first_seen_at=now,
            last_seen_at=now,
            status=IndicatorStatus.ACTIVE,
            verified_by=analyst_user,
            verified_at=now,
        )

        with django_assert_max_num_queries(4):
            res = api_client.post("/api/v1/lookups/", {"query": "fraud-site-test.com"}, format="json")
            assert res.status_code == 200
            assert res.data["verdict"] == "RED"

    def test_lookup_query_count_for_pending_indicator(self, api_client, django_assert_max_num_queries):
        report = ScamReport.objects.create(
            reference_code="SCM-2026-QBOUND1",
            category=ScamCategory.FAKE_JOB,
            platform="WHATSAPP",
            status=ReportStatus.PENDING,
            message_text="Job scam test",
            currency="MYR",
            country_code="MY",
        )
        ReportIndicator.objects.create(
            report=report,
            type=IndicatorType.PHONE,
            raw_value="012-7776665",
            normalized_value="+60127776665",
            display_value="+601•••••6665",
        )

        with django_assert_max_num_queries(4):
            res = api_client.post("/api/v1/lookups/", {"query": "012-7776665"}, format="json")
            assert res.status_code == 200
            assert res.data["verdict"] == "YELLOW"

    def test_lookup_latency_within_300ms(self, api_client, analyst_user):
        """DoD: pasting a scam number shows RED within p95 < 300 ms locally."""
        now = timezone.now()
        VerifiedIndicator.objects.create(
            type=IndicatorType.PHONE,
            normalized_value="+60128889999",
            display_value="+601•••••9999",
            primary_category=ScamCategory.IMPERSONATION,
            threat_level=ThreatLevel.CRITICAL,
            total_report_count=20,
            first_seen_at=now,
            last_seen_at=now,
            status=IndicatorStatus.ACTIVE,
            verified_by=analyst_user,
            verified_at=now,
        )

        # Warm up
        api_client.post("/api/v1/lookups/", {"query": "012-8889999"}, format="json")

        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            res = api_client.post("/api/v1/lookups/", {"query": "012-8889999"}, format="json")
            duration = time.perf_counter() - start
            latencies.append(duration)
            assert res.status_code == 200

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 0.3, f"Lookup latency p95 was {p95:.4f}s, exceeding 300ms limit"
