import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.models import TriageAction, TriageDecision
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.reports.models import (
    Platform,
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
        email="analyst_rej@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_rej@scamshield.gov",
        password="TestPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_rej@example.com",
        password="TestPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestTriageRejectAPI:
    def _create_report(self, status: str = ReportStatus.PENDING) -> ScamReport:
        return ScamReport.objects.create(
            reference_code=f"SCM-2026-REJ-{uuid.uuid4().hex[:6].upper()}",
            category=ScamCategory.ECOMMERCE_FRAUD,
            platform=Platform.FACEBOOK,
            status=status,
            financial_loss=Decimal("50.00"),
            currency="MYR",
            message_text="Possible false report",
            country_code="MY",
        )

    def test_unauthenticated_returns_401(self, api_client):
        report_id = uuid.uuid4()
        resp = api_client.post(
            f"/api/v1/triage/reports/{report_id}/reject/",
            {"reason": "Insufficient evidence"},
            format="json",
        )
        assert resp.status_code == 401

    def test_citizen_and_admin_return_403(self, api_client, citizen_user, admin_user):
        report = self._create_report()

        api_client.force_authenticate(user=citizen_user)
        resp = api_client.post(
            f"/api/v1/triage/reports/{report.id}/reject/",
            {"reason": "Not a scam"},
            format="json",
        )
        assert resp.status_code == 403

        # Admin must NOT have reject permission -> 403
        api_client.force_authenticate(user=admin_user)
        resp_admin = api_client.post(
            f"/api/v1/triage/reports/{report.id}/reject/",
            {"reason": "Not a scam"},
            format="json",
        )
        assert resp_admin.status_code == 403
        assert resp_admin.json()["error"]["code"] == "permission_denied"

    def test_unknown_report_returns_404(self, api_client, analyst_user):
        report_id = uuid.uuid4()
        api_client.force_authenticate(user=analyst_user)
        resp = api_client.post(
            f"/api/v1/triage/reports/{report_id}/reject/",
            {"reason": "Not a scam"},
            format="json",
        )
        assert resp.status_code == 404

    def test_blank_reason_or_too_long_returns_400(self, api_client, analyst_user):
        report = self._create_report()
        api_client.force_authenticate(user=analyst_user)

        # Blank reason
        resp = api_client.post(
            f"/api/v1/triage/reports/{report.id}/reject/",
            {"reason": "   "},
            format="json",
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "validation_error"

        # Missing reason
        resp = api_client.post(
            f"/api/v1/triage/reports/{report.id}/reject/",
            {},
            format="json",
        )
        assert resp.status_code == 400

        # Reason > 500 chars
        resp = api_client.post(
            f"/api/v1/triage/reports/{report.id}/reject/",
            {"reason": "x" * 501},
            format="json",
        )
        assert resp.status_code == 400

    def test_already_resolved_report_returns_409(self, api_client, analyst_user):
        report_ver = self._create_report(status=ReportStatus.VERIFIED)
        report_rej = self._create_report(status=ReportStatus.REJECTED)
        api_client.force_authenticate(user=analyst_user)

        resp_ver = api_client.post(
            f"/api/v1/triage/reports/{report_ver.id}/reject/",
            {"reason": "Second reject attempt"},
            format="json",
        )
        assert resp_ver.status_code == 409
        assert resp_ver.json()["error"]["code"] == "report_already_resolved"

        resp_rej = api_client.post(
            f"/api/v1/triage/reports/{report_rej.id}/reject/",
            {"reason": "Second reject attempt"},
            format="json",
        )
        assert resp_rej.status_code == 409
        assert resp_rej.json()["error"]["code"] == "report_already_resolved"

    def test_successful_rejection_flow(
        self, api_client, analyst_user, django_capture_on_commit_callbacks
    ):
        report = self._create_report(status=ReportStatus.PENDING)
        api_client.force_authenticate(user=analyst_user)

        reason = "Legitimate e-commerce transaction dispute, not a scam."

        with patch("apps.intel.services.triage_service.metrics.emit") as mock_metrics:
            with django_capture_on_commit_callbacks(execute=True):
                resp = api_client.post(
                    f"/api/v1/triage/reports/{report.id}/reject/",
                    {"reason": reason},
                    format="json",
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "REJECTED"
            assert data["reference_code"] == report.reference_code

            # Check metric emitted on commit
            mock_metrics.assert_called_once_with("ReportsRejected")

        # Check DB ScamReport
        report.refresh_from_db()
        assert report.status == ReportStatus.REJECTED
        assert report.reviewed_by == analyst_user
        assert report.reviewed_at is not None
        assert report.review_note == reason

        # Check TriageDecision
        decision = TriageDecision.objects.get(report=report)
        assert decision.analyst == analyst_user
        assert decision.action == TriageAction.REJECT
        assert decision.reason == reason

        # Check Audit log
        audit = SystemAuditLog.objects.filter(
            event_type=AuditEventType.REPORT_REJECTED,
            target_id=str(report.id),
        ).latest("occurred_at")
        assert audit.actor == analyst_user
        assert audit.metadata.get("category") == report.category
