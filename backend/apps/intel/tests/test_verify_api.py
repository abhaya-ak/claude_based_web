import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.models import IndicatorType, ThreatLevel, VerifiedIndicator
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.reports.models import (
    Platform,
    ReportIndicator,
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
        email="analyst_vapi@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_vapi@scamshield.gov",
        password="TestPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_vapi@example.com",
        password="TestPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


def create_report_and_indicator(
    ref: str,
    raw_val: str = "+60188887777",
    status: str = ReportStatus.PENDING,
) -> tuple[ScamReport, ReportIndicator]:
    report = ScamReport.objects.create(
        reference_code=ref,
        category=ScamCategory.PHISHING,
        platform=Platform.WHATSAPP,
        status=status,
        financial_loss=Decimal("20.00"),
        currency="MYR",
        message_text="Phishing text",
        country_code="MY",
    )
    ind = ReportIndicator.objects.create(
        report=report,
        type=IndicatorType.PHONE,
        raw_value=raw_val,
        normalized_value=raw_val,
        display_value=raw_val,
    )
    return report, ind


@pytest.mark.django_db
class TestTriageVerifyAPI:
    def test_unauthenticated_returns_401(self, api_client):
        report_id = uuid.uuid4()
        resp = api_client.post(
            f"/api/v1/triage/reports/{report_id}/verify/",
            {"report_indicator_id": 1},
            format="json",
        )
        assert resp.status_code == 401

    def test_citizen_and_admin_return_403(self, api_client, citizen_user, admin_user):
        report, ind = create_report_and_indicator("SCM-2026-VAPI01")

        api_client.force_authenticate(user=citizen_user)
        assert (
            api_client.post(
                f"/api/v1/triage/reports/{report.id}/verify/",
                {"report_indicator_id": ind.id},
                format="json",
            ).status_code
            == 403
        )

        # Admin must NOT have verify permission -> 403
        api_client.force_authenticate(user=admin_user)
        resp_admin = api_client.post(
            f"/api/v1/triage/reports/{report.id}/verify/",
            {"report_indicator_id": ind.id},
            format="json",
        )
        assert resp_admin.status_code == 403
        assert resp_admin.json()["error"]["code"] == "permission_denied"

    def test_missing_or_mismatched_indicator_returns_400_or_404(
        self, api_client, analyst_user
    ):
        report, ind = create_report_and_indicator("SCM-2026-VAPI02")
        other_report, other_ind = create_report_and_indicator("SCM-2026-OTHER")

        api_client.force_authenticate(user=analyst_user)

        # Missing report_indicator_id
        resp_missing = api_client.post(
            f"/api/v1/triage/reports/{report.id}/verify/",
            {},
            format="json",
        )
        assert resp_missing.status_code == 400

        # Indicator belongs to different report
        resp_wrong = api_client.post(
            f"/api/v1/triage/reports/{report.id}/verify/",
            {"report_indicator_id": other_ind.id},
            format="json",
        )
        assert resp_wrong.status_code in (400, 404)

    def test_already_resolved_report_returns_409(self, api_client, analyst_user):
        report, ind = create_report_and_indicator("SCM-2026-VAPI03", status=ReportStatus.VERIFIED)
        api_client.force_authenticate(user=analyst_user)

        resp = api_client.post(
            f"/api/v1/triage/reports/{report.id}/verify/",
            {"report_indicator_id": ind.id},
            format="json",
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "report_already_resolved"

    def test_successful_verify_api_flow(
        self, api_client, analyst_user, django_capture_on_commit_callbacks
    ):
        r1, ind1 = create_report_and_indicator("SCM-2026-VAPI04", raw_val="+6011223344")
        r2, ind2 = create_report_and_indicator("SCM-2026-VAPI05", raw_val="+6011223344")

        api_client.force_authenticate(user=analyst_user)

        with patch("apps.intel.services.triage_service.metrics.emit") as mock_metrics:
            with django_capture_on_commit_callbacks(execute=True):
                resp = api_client.post(
                    f"/api/v1/triage/reports/{r1.id}/verify/",
                    {
                        "report_indicator_id": ind1.id,
                        "public_note": "Confirmed scam bank recruitment caller.",
                    },
                    format="json",
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["cluster_size"] == 2
            assert data["threat_level"] == ThreatLevel.MEDIUM
            assert len(data["resolved_report_ids"]) == 2
            assert "verified_indicator" in data
            vi_data = data["verified_indicator"]
            assert vi_data["public_note"] == "Confirmed scam bank recruitment caller."

            # Metric emitted on commit
            mock_metrics.assert_called_once_with("IndicatorsVerified")

        # Verify DB state
        r1.refresh_from_db()
        r2.refresh_from_db()
        assert r1.status == ReportStatus.VERIFIED
        assert r2.status == ReportStatus.VERIFIED

        vi = VerifiedIndicator.objects.get(normalized_value="+6011223344")
        assert vi.total_report_count == 2

        # Audit log verification
        audit = SystemAuditLog.objects.filter(
            event_type=AuditEventType.INDICATOR_VERIFIED,
            target_id=str(vi.id),
        ).latest("occurred_at")
        assert audit.actor == analyst_user
        assert audit.metadata.get("cluster_size") == 2
