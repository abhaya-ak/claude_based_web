import uuid
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.models import IndicatorStatus, IndicatorType, ScamCategory, ThreatLevel, VerifiedIndicator
from apps.reports.models import Platform, ReportEvidence, ReportIndicator, ReportStatus, ScamReport
from apps.scanner.models import ScanResult


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_queries@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestTriageQueryCounts:
    """
    Task 6.5 Query Count Assertions:
    - GET /api/v1/triage/queue/ with 15+ pending reports and shared indicators executes <= 3 queries.
    - GET /api/v1/triage/reports/{id}/ with multiple indicators, evidence files, and scan results executes <= 5 queries.
    - GET /api/v1/triage/indicators/ with 15+ indicators executes <= 3 queries.
    """

    def test_triage_queue_query_count(self, analyst_user, django_assert_num_queries):
        client = APIClient()
        client.force_authenticate(user=analyst_user)

        # Create 15 pending reports with shared indicators
        now = timezone.now()
        reports = [
            ScamReport(
                reference_code=f"SCM-2026-Q{i:07d}",
                category=ScamCategory.PHISHING,
                platform=Platform.WHATSAPP,
                financial_loss=Decimal("50.00"),
                currency="MYR",
                incident_date=now.date(),
                message_text=f"Phishing text {i}",
                status=ReportStatus.PENDING,
            )
            for i in range(15)
        ]
        ScamReport.objects.bulk_create(reports)
        created_reports = list(ScamReport.objects.filter(reference_code__startswith="SCM-2026-Q"))

        indicators = [
            ReportIndicator(
                report=r,
                type=IndicatorType.PHONE,
                raw_value="+60188889999",
                normalized_value="+60188889999",
                display_value="+60188889999",
            )
            for r in created_reports
        ]
        ReportIndicator.objects.bulk_create(indicators)

        # GET /api/v1/triage/queue/ executes <= 3 queries (count query, annotated results query)
        with django_assert_num_queries(3, exact=False):
            resp = client.get("/api/v1/triage/queue/")
            assert resp.status_code == 200
            assert resp.data["count"] >= 15

    def test_report_detail_query_count(self, analyst_user, django_assert_num_queries):
        client = APIClient()
        client.force_authenticate(user=analyst_user)

        now = timezone.now()
        report = ScamReport.objects.create(
            reference_code="SCM-2026-DET00001",
            category=ScamCategory.PHISHING,
            platform=Platform.WHATSAPP,
            financial_loss=Decimal("200.00"),
            currency="MYR",
            incident_date=now.date(),
            message_text="Detailed report narrative with lots of details.",
            status=ReportStatus.PENDING,
        )

        # Multiple indicators
        indicators = [
            ReportIndicator(
                report=report,
                type=IndicatorType.URL,
                raw_value=f"https://malicious{i}.com",
                normalized_value=f"https://malicious{i}.com",
                display_value=f"https://malicious{i}.com",
            )
            for i in range(5)
        ]
        ReportIndicator.objects.bulk_create(indicators)

        # Multiple evidence files
        evidence_files = [
            ReportEvidence(
                id=uuid.uuid4(),
                report=report,
                s3_key=f"evidence/{report.id}/{uuid.uuid4()}.png",
                content_type="image/png",
                size_bytes=1024,
                sha256="a" * 64,
            )
            for i in range(3)
        ]
        ReportEvidence.objects.bulk_create(evidence_files)

        # Scan result
        ScanResult.objects.create(
            report=report,
            ruleset_version=1,
            risk_score=75,
            is_high_priority=True,
            breakdown=[{"rule": "scam", "type": "KEYWORD", "points": 10}],
        )

        # GET /api/v1/triage/reports/{id}/ executes <= 5 queries
        with django_assert_num_queries(5, exact=False):
            resp = client.get(f"/api/v1/triage/reports/{report.id}/")
            assert resp.status_code == 200
            assert resp.data["reference_code"] == "SCM-2026-DET00001"
            assert len(resp.data["indicators"]) == 5
            assert len(resp.data["evidence_files"]) == 3
            assert resp.data["scan_result"] is not None

    def test_indicators_list_query_count(self, analyst_user, django_assert_num_queries):
        client = APIClient()
        client.force_authenticate(user=analyst_user)

        now = timezone.now()
        indicators = [
            VerifiedIndicator(
                id=uuid.uuid4(),
                type=IndicatorType.PHONE,
                normalized_value=f"+6012345{i:04d}",
                display_value=f"+6012345{i:04d}",
                primary_category=ScamCategory.PHISHING,
                threat_level=ThreatLevel.MEDIUM,
                total_report_count=i + 1,
                first_seen_at=now,
                last_seen_at=now,
                status=IndicatorStatus.ACTIVE,
                public_note=f"Note {i}",
                verified_by=analyst_user,
                verified_at=now,
            )
            for i in range(15)
        ]
        VerifiedIndicator.objects.bulk_create(indicators)

        # GET /api/v1/triage/indicators/ executes <= 3 queries (count query, select results query)
        with django_assert_num_queries(3, exact=False):
            resp = client.get("/api/v1/triage/indicators/")
            assert resp.status_code == 200
            assert resp.data["count"] >= 15
