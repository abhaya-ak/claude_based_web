import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.models import IndicatorStatus, IndicatorType, ScamCategory, ThreatLevel, VerifiedIndicator
from apps.ops.models import AuditEventType, SystemAuditLog


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_ind@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_ind@scamshield.gov",
        password="TestPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_user(db):
    return User.objects.create_user(
        email="educator_ind@scamshield.gov",
        password="TestPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_ind@example.com",
        password="TestPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def pending_analyst(db):
    return User.objects.create_user(
        email="pending_analyst_ind@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.PENDING,
    )


def create_verified_indicator(
    analyst,
    itype: str = IndicatorType.PHONE,
    norm_val: str = "+60123456789",
    threat_level: str = ThreatLevel.MEDIUM,
    status: str = IndicatorStatus.ACTIVE,
    public_note: str = "Known scammer",
    offset_hours: int = 0,
) -> VerifiedIndicator:
    now = timezone.now() - timedelta(hours=offset_hours)
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
        public_note=public_note,
        verified_by=analyst,
        verified_at=now,
    )


@pytest.mark.django_db
class TestIndicatorsListAPI:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get("/api/v1/triage/indicators/")
        assert resp.status_code == 401

    def test_forbidden_roles_return_403(self, api_client, citizen_user, educator_user, pending_analyst):
        for user in [citizen_user, educator_user, pending_analyst]:
            api_client.force_authenticate(user=user)
            resp = api_client.get("/api/v1/triage/indicators/")
            assert resp.status_code == 403

    def test_analyst_and_admin_allowed_paginated(self, api_client, analyst_user, admin_user):
        create_verified_indicator(analyst_user, norm_val="+60111111111")
        create_verified_indicator(analyst_user, norm_val="+60222222222")

        for user in [analyst_user, admin_user]:
            api_client.force_authenticate(user=user)
            resp = api_client.get("/api/v1/triage/indicators/")
            assert resp.status_code == 200
            assert "results" in resp.data
            assert resp.data["count"] == 2

    def test_filter_by_type_and_threat_level_and_status(self, api_client, analyst_user):
        api_client.force_authenticate(user=analyst_user)
        create_verified_indicator(
            analyst_user, itype=IndicatorType.PHONE, norm_val="+60111111111", threat_level=ThreatLevel.MEDIUM
        )
        vi_url = create_verified_indicator(
            analyst_user, itype=IndicatorType.URL, norm_val="https://scam.org", threat_level=ThreatLevel.CRITICAL
        )
        vi_revoked = create_verified_indicator(
            analyst_user,
            itype=IndicatorType.PHONE,
            norm_val="+60333333333",
            status=IndicatorStatus.REVOKED,
        )

        # Filter by type
        resp = api_client.get("/api/v1/triage/indicators/?type=URL")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["id"] == str(vi_url.id)

        # Filter by threat_level
        resp = api_client.get("/api/v1/triage/indicators/?threat_level=CRITICAL")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["id"] == str(vi_url.id)

        # Filter by status
        resp = api_client.get("/api/v1/triage/indicators/?status=REVOKED")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["id"] == str(vi_revoked.id)

    def test_invalid_filter_enum_returns_400(self, api_client, analyst_user):
        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get("/api/v1/triage/indicators/?type=INVALID")
        assert resp.status_code == 400
        assert resp.data["error"]["code"] == "validation_error"

        resp = api_client.get("/api/v1/triage/indicators/?threat_level=LOW")
        assert resp.status_code == 400
        assert resp.data["error"]["code"] == "validation_error"

        resp = api_client.get("/api/v1/triage/indicators/?status=PENDING")
        assert resp.status_code == 400
        assert resp.data["error"]["code"] == "validation_error"

    def test_search_filter(self, api_client, analyst_user):
        api_client.force_authenticate(user=analyst_user)
        create_verified_indicator(
            analyst_user, norm_val="+60199998888", public_note="Telegram crypto pump"
        )
        create_verified_indicator(
            analyst_user, norm_val="+60177776666", public_note="Standard phishing"
        )

        resp = api_client.get("/api/v1/triage/indicators/?search=Telegram")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["normalized_value"] == "+60199998888"

        resp = api_client.get("/api/v1/triage/indicators/?search=7777")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["normalized_value"] == "+60177776666"


@pytest.mark.django_db
class TestIndicatorDetailAPI:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(f"/api/v1/triage/indicators/{uuid.uuid4()}/")
        assert resp.status_code == 401

    def test_citizen_returns_403(self, api_client, citizen_user):
        api_client.force_authenticate(user=citizen_user)
        resp = api_client.get(f"/api/v1/triage/indicators/{uuid.uuid4()}/")
        assert resp.status_code == 403

    def test_not_found_returns_404(self, api_client, analyst_user):
        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get(f"/api/v1/triage/indicators/{uuid.uuid4()}/")
        assert resp.status_code == 404

    def test_analyst_and_admin_return_full_detail(self, api_client, analyst_user, admin_user):
        vi = create_verified_indicator(analyst_user)
        for user in [analyst_user, admin_user]:
            api_client.force_authenticate(user=user)
            resp = api_client.get(f"/api/v1/triage/indicators/{vi.id}/")
            assert resp.status_code == 200
            assert resp.data["id"] == str(vi.id)
            assert resp.data["normalized_value"] == vi.normalized_value


@pytest.mark.django_db
class TestIndicatorCurationAPI:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.patch(f"/api/v1/triage/indicators/{uuid.uuid4()}/", {"public_note": "New note"})
        assert resp.status_code == 401

    def test_citizen_and_admin_forbidden(self, api_client, citizen_user, admin_user):
        vi_id = uuid.uuid4()
        for user in [citizen_user, admin_user]:
            api_client.force_authenticate(user=user)
            resp = api_client.patch(f"/api/v1/triage/indicators/{vi_id}/", {"public_note": "New note"})
            assert resp.status_code == 403

    def test_analyst_updates_public_note_successfully(self, api_client, analyst_user):
        vi = create_verified_indicator(analyst_user, public_note="Initial note")
        api_client.force_authenticate(user=analyst_user)

        resp = api_client.patch(
            f"/api/v1/triage/indicators/{vi.id}/",
            {"public_note": "Updated public intelligence note"},
        )
        assert resp.status_code == 200
        assert resp.data["public_note"] == "Updated public intelligence note"

        vi.refresh_from_db()
        assert vi.public_note == "Updated public intelligence note"

    def test_curation_rejects_exceeding_500_chars(self, api_client, analyst_user):
        vi = create_verified_indicator(analyst_user)
        api_client.force_authenticate(user=analyst_user)

        resp = api_client.patch(
            f"/api/v1/triage/indicators/{vi.id}/",
            {"public_note": "x" * 501},
        )
        assert resp.status_code == 400
        assert resp.data["error"]["code"] == "validation_error"

    def test_curation_rejects_read_only_fields(self, api_client, analyst_user):
        vi = create_verified_indicator(analyst_user)
        api_client.force_authenticate(user=analyst_user)

        resp = api_client.patch(
            f"/api/v1/triage/indicators/{vi.id}/",
            {"public_note": "Valid note", "threat_level": "CRITICAL"},
        )
        assert resp.status_code == 400
        assert resp.data["error"]["code"] == "validation_error"


@pytest.mark.django_db
class TestIndicatorRevocationAPI:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.post(f"/api/v1/triage/indicators/{uuid.uuid4()}/revoke/", {"reason": "Revoke"})
        assert resp.status_code == 401

    def test_admin_and_citizen_forbidden(self, api_client, citizen_user, admin_user):
        vi_id = uuid.uuid4()
        for user in [citizen_user, admin_user]:
            api_client.force_authenticate(user=user)
            resp = api_client.post(f"/api/v1/triage/indicators/{vi_id}/revoke/", {"reason": "Revoke"})
            assert resp.status_code == 403

    def test_blank_or_invalid_reason_returns_400(self, api_client, analyst_user):
        vi = create_verified_indicator(analyst_user)
        api_client.force_authenticate(user=analyst_user)

        # Missing reason
        resp = api_client.post(f"/api/v1/triage/indicators/{vi.id}/revoke/", {})
        assert resp.status_code == 400
        assert resp.data["error"]["code"] == "validation_error"

        # Blank reason
        resp = api_client.post(f"/api/v1/triage/indicators/{vi.id}/revoke/", {"reason": "   "})
        assert resp.status_code == 400
        assert resp.data["error"]["code"] == "validation_error"

        # Exceeds 300 chars
        resp = api_client.post(f"/api/v1/triage/indicators/{vi.id}/revoke/", {"reason": "r" * 301})
        assert resp.status_code == 400
        assert resp.data["error"]["code"] == "validation_error"

    def test_analyst_revokes_active_indicator_successfully(
        self, api_client, analyst_user, django_capture_on_commit_callbacks
    ):
        vi = create_verified_indicator(analyst_user, status=IndicatorStatus.ACTIVE)
        api_client.force_authenticate(user=analyst_user)

        with patch("apps.intel.services.triage_service.metrics.emit") as mock_metric:
            with django_capture_on_commit_callbacks(execute=True):
                resp = api_client.post(
                    f"/api/v1/triage/indicators/{vi.id}/revoke/",
                    {"reason": "Legitimate enterprise number falsely flagged."},
                )

        assert resp.status_code == 200
        assert resp.data["status"] == "REVOKED"
        assert resp.data["revoke_reason"] == "Legitimate enterprise number falsely flagged."
        assert str(resp.data["revoked_by_id"]) == str(analyst_user.id)
        assert resp.data["revoked_at"] is not None

        vi.refresh_from_db()
        assert vi.status == IndicatorStatus.REVOKED
        assert vi.revoked_by == analyst_user
        assert vi.revoke_reason == "Legitimate enterprise number falsely flagged."

        # Verify audit log
        audit_log = SystemAuditLog.objects.filter(
            event_type=AuditEventType.INDICATOR_REVOKED,
            target_id=str(vi.id),
        ).latest("occurred_at")
        assert audit_log.actor == analyst_user
        assert audit_log.metadata["threat_level"] == vi.threat_level
        assert audit_log.metadata["indicator_type"] == vi.type

        # Verify metric emitted
        mock_metric.assert_called_with("IndicatorsRevoked")

    def test_revoking_already_revoked_indicator_returns_409(self, api_client, analyst_user):
        vi = create_verified_indicator(analyst_user, status=IndicatorStatus.REVOKED)
        api_client.force_authenticate(user=analyst_user)

        resp = api_client.post(
            f"/api/v1/triage/indicators/{vi.id}/revoke/",
            {"reason": "Trying to revoke again"},
        )
        assert resp.status_code == 409
        assert resp.data["error"]["code"] == "indicator_already_revoked"
