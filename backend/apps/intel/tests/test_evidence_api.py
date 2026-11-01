import uuid
from decimal import Decimal

import pytest
from moto import mock_aws
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.aws import client, reset_clients
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.reports.models import (
    Platform,
    ReportEvidence,
    ReportStatus,
    ScamCategory,
    ScamReport,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_ev@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_ev@scamshield.gov",
        password="TestPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_ev@example.com",
        password="TestPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_user(db):
    return User.objects.create_user(
        email="educator_ev@example.com",
        password="TestPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestTriageEvidenceAPI:
    def _create_report_with_evidence(self) -> tuple[ScamReport, list[ReportEvidence]]:
        report = ScamReport.objects.create(
            reference_code="SCM-2026-EV01",
            category=ScamCategory.PHISHING,
            platform=Platform.WHATSAPP,
            status=ReportStatus.PENDING,
            financial_loss=Decimal("0.00"),
            currency="MYR",
            message_text="Report with evidence files",
            country_code="MY",
        )
        ev1 = ReportEvidence.objects.create(
            report=report,
            s3_key=f"evidence/{report.id}/file1.png",
            content_type="image/png",
            size_bytes=2048,
            sha256="1" * 64,
        )
        ev2 = ReportEvidence.objects.create(
            report=report,
            s3_key=f"evidence/{report.id}/file2.pdf",
            content_type="application/pdf",
            size_bytes=4096,
            sha256="2" * 64,
        )
        return report, [ev1, ev2]

    def test_unauthenticated_returns_401(self, api_client):
        report_id = uuid.uuid4()
        resp = api_client.get(f"/api/v1/triage/reports/{report_id}/evidence/")
        assert resp.status_code == 401

    def test_citizen_educator_and_admin_return_403(
        self, api_client, citizen_user, educator_user, admin_user
    ):
        report, _ = self._create_report_with_evidence()

        api_client.force_authenticate(user=citizen_user)
        assert api_client.get(f"/api/v1/triage/reports/{report.id}/evidence/").status_code == 403

        api_client.force_authenticate(user=educator_user)
        assert api_client.get(f"/api/v1/triage/reports/{report.id}/evidence/").status_code == 403

        # Admin must NOT have evidence access -> 403
        api_client.force_authenticate(user=admin_user)
        resp_admin = api_client.get(f"/api/v1/triage/reports/{report.id}/evidence/")
        assert resp_admin.status_code == 403
        assert resp_admin.json()["error"]["code"] == "permission_denied"

    def test_unknown_report_returns_404(self, api_client, analyst_user):
        report_id = uuid.uuid4()
        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get(f"/api/v1/triage/reports/{report_id}/evidence/")
        assert resp.status_code == 404

    @mock_aws
    def test_analyst_receives_presigned_urls_and_audits_event(
        self, api_client, analyst_user, settings
    ):
        settings.EVIDENCE_BUCKET = "scamshield-evidence-test"
        reset_clients()
        s3 = client("s3")
        s3.create_bucket(
            Bucket=settings.EVIDENCE_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )

        report, evidence_files = self._create_report_with_evidence()

        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get(f"/api/v1/triage/reports/{report.id}/evidence/")
        assert resp.status_code == 200
        data = resp.json()

        assert len(data) == 2
        ev_map = {item["id"]: item for item in data}

        for ev in evidence_files:
            item = ev_map[str(ev.id)]
            assert item["size_bytes"] == ev.size_bytes
            assert item["content_type"] == ev.content_type
            assert item["expires_in"] == 900
            assert "download_url" in item
            url = item["download_url"]
            # Presigned URL checks
            assert "ResponseContentDisposition=attachment" in url or "response-content-disposition=attachment" in url.lower()
            assert "X-Amz-Expires=900" in url or "Expires=" in url

        # Audit row verification
        audit = SystemAuditLog.objects.filter(
            event_type=AuditEventType.EVIDENCE_URL_ISSUED,
            target_id=str(report.id),
        ).latest("occurred_at")
        assert audit.actor == analyst_user
        assert audit.metadata.get("file_count") == 2
