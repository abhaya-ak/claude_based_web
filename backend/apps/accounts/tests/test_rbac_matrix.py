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

    # 20. POST /api/v1/lookups/ (Public endpoint, accessible to all)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 200),
            ("citizen", 200),
            ("analyst_pending", 200),
            ("analyst_approved", 200),
            ("educator_approved", 200),
            ("admin_pending", 200),
            ("admin_approved", 200),
        ],
    )
    def test_lookup_access_all_roles(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.post(
            "/api/v1/lookups/",
            data={"query": "innocent-site.org"},
            format="json",
        )
        assert response.status_code == expected_status

    # 21. POST /api/v1/alerts/subscriptions/ (Public endpoint, accessible to all)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 201),
            ("citizen", 201),
            ("analyst_pending", 201),
            ("analyst_approved", 201),
            ("educator_approved", 201),
            ("admin_pending", 201),
            ("admin_approved", 201),
        ],
    )
    def test_alert_subscription_access_all_roles(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        suffix = user_attr or "anon"
        response = client.post(
            "/api/v1/alerts/subscriptions/",
            data={
                "channel": "EMAIL",
                "endpoint": f"user_{suffix}@subscriber-test.com",
                "audience": "GENERAL",
            },
            format="json",
        )
        assert response.status_code == expected_status

    # 22. GET /api/v1/analytics/volume/ (ANALYST and ADMIN only)
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
    def test_analytics_volume_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/analytics/volume/")
        assert response.status_code == expected_status

    # 23. GET /api/v1/advisories/ (Public endpoint, accessible to all)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 200),
            ("citizen", 200),
            ("analyst_pending", 200),
            ("analyst_approved", 200),
            ("educator_approved", 200),
            ("admin_pending", 200),
            ("admin_approved", 200),
        ],
    )
    def test_advisories_list_access_all_roles(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/advisories/")
        assert response.status_code == expected_status

    # 24. POST /api/v1/advisories/ (ANALYST only)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 201),
            ("educator_approved", 403),
            ("admin_pending", 403),
            ("admin_approved", 403),
        ],
    )
    def test_advisories_create_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.post(
            "/api/v1/advisories/",
            data={
                "title": f"Advisory from {user_attr}",
                "body": "Detailed warning text for the public.",
                "sms_text": "Short warning.",
                "severity": "WARNING",
                "target_audience": "GENERAL",
                "category": "PHISHING",
            },
            format="json",
        )
        assert response.status_code == expected_status

    # 25. POST /api/v1/advisories/{id}/publish/ (ANALYST only)
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
    def test_advisories_publish_access(self, user_attr, expected_status, settings):
        import boto3
        from moto import mock_aws

        from apps.broadcasts.models import AdvisorySeverity, AdvisoryStatus, ThreatAdvisory
        from apps.core.aws import reset_clients

        with mock_aws():
            reset_clients()
            sns = boto3.client("sns", region_name="ap-southeast-1")
            topic = sns.create_topic(Name="scamshield-alerts")
            settings.ALERTS_TOPIC_ARN = topic["TopicArn"]

            advisory = ThreatAdvisory.objects.create(
                title=f"Advisory to publish {user_attr}",
                body="Body text",
                sms_text="SMS text",
                severity=AdvisorySeverity.WARNING,
                target_audience="GENERAL",
                status=AdvisoryStatus.DRAFT,
                created_by=self.analyst_approved,
            )

            user = getattr(self, user_attr) if user_attr else None
            client = self._client_for(user)
            response = client.post(f"/api/v1/advisories/{advisory.id}/publish/")
            assert response.status_code == expected_status
            reset_clients()

    # 26. GET /api/v1/studio/guides/ (EDUCATOR or ADMIN approved)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 200),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_studio_guides_list_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/studio/guides/")
        assert response.status_code == expected_status

    # 27. POST /api/v1/studio/guides/ (EDUCATOR or ADMIN approved)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 201),
            ("admin_pending", 403),
            ("admin_approved", 201),
        ],
    )
    def test_studio_guides_create_access(self, user_attr, expected_status):
        from apps.core.enums import AudienceGroup
        from apps.literacy.models import Tactic

        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        payload = {
            "title": f"Test Guide RBAC {user_attr}",
            "summary": "Summary",
            "body": "Body content",
            "audience_groups": [AudienceGroup.GENERAL.value],
            "tactics": [Tactic.URGENCY.value],
            "language": "en",
        }
        response = client.post("/api/v1/studio/guides/", payload, format="json")
        assert response.status_code == expected_status

    # 28. GET /api/v1/guides/ (Public Hub: AllowAny)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 200),
            ("citizen", 200),
            ("analyst_pending", 200),
            ("analyst_approved", 200),
            ("educator_approved", 200),
            ("admin_pending", 200),
            ("admin_approved", 200),
        ],
    )
    def test_public_guides_list_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/guides/")
        assert response.status_code == expected_status

    # 29. GET /api/v1/studio/scenarios/ (EDUCATOR or ADMIN approved)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 200),
            ("admin_pending", 403),
            ("admin_approved", 200),
        ],
    )
    def test_studio_scenarios_list_access(self, user_attr, expected_status):
        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.get("/api/v1/studio/scenarios/")
        assert response.status_code == expected_status

    # 30. POST /api/v1/studio/scenarios/ (EDUCATOR or ADMIN approved)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 401),
            ("citizen", 403),
            ("analyst_pending", 403),
            ("analyst_approved", 403),
            ("educator_approved", 201),
            ("admin_pending", 403),
            ("admin_approved", 201),
        ],
    )
    def test_studio_scenarios_create_access(self, user_attr, expected_status):
        import io

        import boto3
        from moto import mock_aws

        from apps.core.aws import reset_clients
        from apps.literacy.models import ScenarioChannel, ScenarioTactic

        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)

        valid_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
            b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        img = io.BytesIO(valid_png)
        img.name = "test.png"

        payload = {
            "title": f"Test Scenario RBAC {user_attr}",
            "channel": ScenarioChannel.SMS.value,
            "is_scam": True,
            "tactic": ScenarioTactic.URGENCY.value,
            "difficulty": 1,
            "image_alt": "Alt text",
            "explanation": "Explanation",
            "image": img,
        }

        with mock_aws():
            reset_clients()
            s3 = boto3.client("s3", region_name="ap-southeast-1")
            s3.create_bucket(
                Bucket="scamshield-media-test",
                CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
            )
            response = client.post("/api/v1/studio/scenarios/", payload, format="multipart")
            reset_clients()

        assert response.status_code == expected_status

    # 31. POST /api/v1/simulator/attempts/ (Public simulator attempt init: AllowAny)
    @pytest.mark.parametrize(
        "user_attr,expected_status",
        [
            (None, 201),
            ("citizen", 201),
            ("analyst_pending", 201),
            ("analyst_approved", 201),
            ("educator_approved", 201),
            ("admin_pending", 201),
            ("admin_approved", 201),
        ],
    )
    def test_simulator_attempt_init_access(self, user_attr, expected_status):
        from apps.literacy.models import ScenarioChannel, ScenarioStatus, ScenarioTactic, SimulatorScenario

        if SimulatorScenario.objects.filter(status=ScenarioStatus.PUBLISHED).count() < 5:
            for i in range(5):
                SimulatorScenario.objects.create(
                    title=f"RBAC Sim Scenario {i}",
                    channel=ScenarioChannel.EMAIL.value,
                    is_scam=False,
                    tactic=ScenarioTactic.NONE.value,
                    difficulty=1,
                    image_s3_key=f"scenarios/rbac_{i}.png",
                    image_alt="Alt",
                    explanation="Exp",
                    status=ScenarioStatus.PUBLISHED,
                    author=self.admin_approved,
                )

        user = getattr(self, user_attr) if user_attr else None
        client = self._client_for(user)
        response = client.post("/api/v1/simulator/attempts/", {}, format="json")
        assert response.status_code == expected_status

