import uuid
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role
from apps.accounts.tests.factories import UserFactory
from apps.intel.models import IndicatorStatus, IndicatorType, ScamCategory, ThreatLevel, VerifiedIndicator
from apps.reports.models import Platform, ReportEvidence, ReportIndicator, ReportStatus, ScamReport


@pytest.mark.django_db
class TestRBACMatrix:
    """
    Comprehensive RBAC Matrix Test across 7 user states and all Phase 3 endpoints:
    - Anonymous
    - CITIZEN (APPROVED)
    - ANALYST (PENDING)
    - ANALYST (APPROVED)
    - EDUCATOR (APPROVED)
    - ADMIN (PENDING)
    - ADMIN (APPROVED)
    """

    @pytest.fixture(autouse=True)
    def setup_users(self):
        self.password = "ValidPass12345!"
        self.citizen = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        self.citizen.set_password(self.password)
        self.citizen.save()

        self.analyst_pending = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.PENDING)
        self.analyst_pending.set_password(self.password)
        self.analyst_pending.save()

        self.analyst_approved = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.APPROVED)
        self.analyst_approved.set_password(self.password)
        self.analyst_approved.save()

        self.educator_approved = UserFactory(role=Role.EDUCATOR, approval_status=ApprovalStatus.APPROVED)
        self.educator_approved.set_password(self.password)
        self.educator_approved.save()

        self.admin_pending = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.PENDING)
        self.admin_pending.set_password(self.password)
        self.admin_pending.save()

        self.admin_approved = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        self.admin_approved.set_password(self.password)
        self.admin_approved.save()

        # Target users for admin operations
        self.target_pending = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.PENDING)
        self.target_staff = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.APPROVED)
        # Second admin so self-change or last-admin rules don't interfere
        self.second_admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)

    def _client_for(self, user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return client

    # 1. /api/v1/auth/me/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 200),
            ("analyst_pending", 200),
            ("analyst_approved", 200),
            ("educator_approved", 200),
            ("admin_pending", 200),
            ("admin_approved", 200),
        ],
    )
    def test_auth_me_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/auth/me/")
        assert response.status_code == expected_status

    # 2. /api/v1/auth/password/change/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 204),
            ("analyst_pending", 204),
            ("analyst_approved", 204),
            ("educator_approved", 204),
            ("admin_pending", 204),
            ("admin_approved", 204),
        ],
    )
    def test_auth_password_change_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        payload = {
            "current_password": self.password,
            "new_password": "NewSecretPass987!",
        }
        response = client.post("/api/v1/auth/password/change/", data=payload, format="json")
        assert response.status_code == expected_status

    # 3. GET /api/v1/admin-portal/users/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_admin_portal_list_users_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/admin-portal/users/")
        assert response.status_code == expected_status

    # 4. POST /api/v1/admin-portal/users/{id}/approve/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_admin_portal_approve_user_access(self, user_attr, expected_status):
        target = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.PENDING)
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.post(f"/api/v1/admin-portal/users/{target.id}/approve/")
        assert response.status_code == expected_status

    # 5. POST /api/v1/admin-portal/users/{id}/reject/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_admin_portal_reject_user_access(self, user_attr, expected_status):
        target = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.PENDING)
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.post(
            f"/api/v1/admin-portal/users/{target.id}/reject/",
            data={"reason": "Incomplete verification documents"},
            format="json",
        )
        assert response.status_code == expected_status

    # 6. POST /api/v1/admin-portal/users/{id}/change-role/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_admin_portal_change_role_access(self, user_attr, expected_status):
        target = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.APPROVED)
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.post(
            f"/api/v1/admin-portal/users/{target.id}/change-role/",
            data={"role": Role.EDUCATOR},
            format="json",
        )
        assert response.status_code == expected_status

    # 7. GET /api/v1/reports/options/ (public per D54)
    @pytest.mark.parametrize(
        "user_attr",
        [
            None,
            "citizen",
            "analyst_pending",
            "analyst_approved",
            "educator_approved",
            "admin_pending",
            "admin_approved",
        ],
    )
    def test_reports_options_access(self, user_attr):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/reports/options/")
        assert response.status_code == 200

    # 8. GET /api/v1/reports/mine/ (authenticated only per D54)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 200),
            ("analyst_pending", 200),
            ("analyst_approved", 200),
            ("educator_approved", 200),
            ("admin_pending", 200),
            ("admin_approved", 200),
        ],
    )
    def test_reports_mine_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/reports/mine/")
        assert response.status_code == expected_status


    # 9. GET /api/v1/admin-portal/rules/ (ADMIN only per D84)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_admin_portal_rules_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/admin-portal/rules/")
        assert response.status_code == expected_status

    # 10. GET /api/v1/admin-portal/scanner-config/ (ADMIN only per D85)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_admin_portal_scanner_config_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/admin-portal/scanner-config/")
        assert response.status_code == expected_status

    def _create_triage_fixtures(self):
        now = timezone.now()
        report = ScamReport.objects.create(
            reference_code=f"SCM-2026-{uuid.uuid4().hex[:8].upper()}",
            category=ScamCategory.PHISHING,
            platform=Platform.WHATSAPP,
            financial_loss=Decimal("100.00"),
            currency="MYR",
            incident_date=now.date(),
            message_text="Phishing scam narrative text",
            status=ReportStatus.PENDING,
        )
        ri = ReportIndicator.objects.create(
            report=report,
            type=IndicatorType.PHONE,
            raw_value="+60123456789",
            normalized_value="+60123456789",
            display_value="+60123456789",
        )
        evidence = ReportEvidence.objects.create(
            id=uuid.uuid4(),
            report=report,
            s3_key=f"evidence/{report.id}/{uuid.uuid4()}.png",
            content_type="image/png",
            size_bytes=1024,
            sha256="b" * 64,
        )
        indicator = VerifiedIndicator.objects.create(
            id=uuid.uuid4(),
            type=IndicatorType.PHONE,
            normalized_value=f"+60199{uuid.uuid4().hex[:6]}",
            display_value="+60199...",
            primary_category=ScamCategory.PHISHING,
            threat_level=ThreatLevel.MEDIUM,
            total_report_count=1,
            first_seen_at=now,
            last_seen_at=now,
            status=IndicatorStatus.ACTIVE,
            public_note="Initial public note",
            verified_by=self.analyst_approved,
            verified_at=now,
        )
        return report, ri, evidence, indicator

    # 11. GET /api/v1/triage/queue/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 200),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_triage_queue_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/triage/queue/")
        assert response.status_code == expected_status

    # 12. GET /api/v1/triage/reports/{id}/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 200),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_triage_report_detail_access(self, user_attr, expected_status):
        report, _, _, _ = self._create_triage_fixtures()
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get(f"/api/v1/triage/reports/{report.id}/")
        assert response.status_code == expected_status

    # 13. GET /api/v1/triage/reports/{id}/evidence/ (ANALYST only)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 200),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 403),
        ],
    )
    def test_triage_report_evidence_access(self, user_attr, expected_status):
        report, _, _, _ = self._create_triage_fixtures()
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get(f"/api/v1/triage/reports/{report.id}/evidence/")
        assert response.status_code == expected_status

    # 14. POST /api/v1/triage/reports/{id}/verify/ (ANALYST only)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 200),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 403),
        ],
    )
    def test_triage_report_verify_access(self, user_attr, expected_status):
        report, ri, _, _ = self._create_triage_fixtures()
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.post(
            f"/api/v1/triage/reports/{report.id}/verify/",
            data={"report_indicator_id": ri.id},
            format="json",
        )
        assert response.status_code == expected_status

    # 15. POST /api/v1/triage/reports/{id}/reject/ (ANALYST only)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 200),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 403),
        ],
    )
    def test_triage_report_reject_access(self, user_attr, expected_status):
        report, _, _, _ = self._create_triage_fixtures()
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.post(
            f"/api/v1/triage/reports/{report.id}/reject/",
            data={"reason": "Dispute, not scam"},
            format="json",
        )
        assert response.status_code == expected_status

    # 16. GET /api/v1/triage/indicators/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 200),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_triage_indicators_list_access(self, user_attr, expected_status):
        self._create_triage_fixtures()
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/triage/indicators/")
        assert response.status_code == expected_status

    # 17. GET /api/v1/triage/indicators/{id}/
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 200),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_triage_indicator_detail_access(self, user_attr, expected_status):
        _, _, _, vi = self._create_triage_fixtures()
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get(f"/api/v1/triage/indicators/{vi.id}/")
        assert response.status_code == expected_status

    # 18. PATCH /api/v1/triage/indicators/{id}/ (ANALYST only)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 200),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 403),
        ],
    )
    def test_triage_indicator_patch_access(self, user_attr, expected_status):
        _, _, _, vi = self._create_triage_fixtures()
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.patch(
            f"/api/v1/triage/indicators/{vi.id}/",
            data={"public_note": "Curation update"},
            format="json",
        )
        assert response.status_code == expected_status

    # 19. POST /api/v1/triage/indicators/{id}/revoke/ (ANALYST only)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 200),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 403),
        ],
    )
    def test_triage_indicator_revoke_access(self, user_attr, expected_status):
        _, _, _, vi = self._create_triage_fixtures()
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.post(
            f"/api/v1/triage/indicators/{vi.id}/revoke/",
            data={"reason": "False alarm"},
            format="json",
        )
        assert response.status_code == expected_status
