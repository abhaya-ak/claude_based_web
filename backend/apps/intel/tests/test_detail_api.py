import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.reports.models import (
    IndicatorType,
    Platform,
    ReportEvidence,
    ReportIndicator,
    ReportStatus,
    ScamCategory,
    ScamReport,
)
from apps.scanner.models import ScanResult


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@scamshield.gov",
        password="TestPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen@example.com",
        password="TestPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestTriageDetailAPI:
    def test_unauthenticated_returns_401(self, api_client):
        report_id = uuid.uuid4()
        resp = api_client.get(f"/api/v1/triage/reports/{report_id}/")
        assert resp.status_code == 401

    def test_citizen_returns_403(self, api_client, citizen_user):
        report_id = uuid.uuid4()
        api_client.force_authenticate(user=citizen_user)
        resp = api_client.get(f"/api/v1/triage/reports/{report_id}/")
        assert resp.status_code == 403

    def test_unknown_report_returns_404(self, api_client, analyst_user):
        report_id = uuid.uuid4()
        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get(f"/api/v1/triage/reports/{report_id}/")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_analyst_and_admin_return_full_detail(self, api_client, analyst_user, admin_user):
        report = ScamReport.objects.create(
            reference_code="SCM-2026-DET01",
            category=ScamCategory.PHISHING,
            platform=Platform.WHATSAPP,
            status=ReportStatus.PENDING,
            financial_loss=Decimal("250.00"),
            currency="MYR",
            message_text="Confidential victim narrative that analyst needs to inspect",
            country_code="MY",
            risk_score=85,
            is_high_priority=True,
        )
        ind1 = ReportIndicator.objects.create(
            report=report,
            type=IndicatorType.PHONE,
            raw_value="+60123456789",
            normalized_value="+60123456789",
            display_value="+60123456789",
        )
        ev1 = ReportEvidence.objects.create(
            report=report,
            s3_key=f"evidence/{report.id}/sample.png",
            content_type="image/png",
            size_bytes=1024,
            sha256="a" * 64,
        )
        ScanResult.objects.create(
            report=report,
            ruleset_version=1,
            risk_score=85,
            is_high_priority=True,
            breakdown=[{"rule": "urgent", "points": 45}],
        )

        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get(f"/api/v1/triage/reports/{report.id}/")
        assert resp.status_code == 200
        data = resp.json()

        # Metadata
        assert data["id"] == str(report.id)
        assert data["reference_code"] == "SCM-2026-DET01"
        assert data["status"] == "PENDING"
        assert data["category"] == "PHISHING"
        assert data["platform"] == "WHATSAPP"
        assert data["financial_loss"] == "250.00"
        assert data["currency"] == "MYR"
        assert data["risk_score"] == 85
        assert data["is_high_priority"] is True

        # Narrative
        assert data["message_text"] == "Confidential victim narrative that analyst needs to inspect"

        # Indicators
        assert len(data["indicators"]) == 1
        ind_data = data["indicators"][0]
        assert ind_data["id"] == ind1.id
        assert ind_data["type"] == "PHONE"
        assert ind_data["raw_value"] == "+60123456789"
        assert ind_data["normalized_value"] == "+60123456789"

        # Evidence metadata (NO presigned URLs here)
        assert len(data["evidence_files"]) == 1
        ev_data = data["evidence_files"][0]
        assert ev_data["id"] == str(ev1.id)
        assert ev_data["content_type"] == "image/png"
        assert ev_data["size_bytes"] == 1024
        assert "download_url" not in ev_data
        assert "url" not in ev_data

        # Scan breakdown
        assert data["scan_result"] is not None
        assert data["scan_result"]["ruleset_version"] == 1
        assert data["scan_result"]["risk_score"] == 85
        assert data["scan_result"]["breakdown"] == [{"rule": "urgent", "points": 45}]

        # Cluster size
        assert data["cluster_size"] == 1

        # Admin also gets 200
        api_client.force_authenticate(user=admin_user)
        resp_admin = api_client.get(f"/api/v1/triage/reports/{report.id}/")
        assert resp_admin.status_code == 200
