import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.scanner.models import ScannerConfig


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_cfg@example.com",
        password="AdminPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_cfg@example.com",
        password="CitizenPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def citizen_client(citizen_user):
    client = APIClient()
    client.force_authenticate(user=citizen_user)
    return client


@pytest.mark.django_db
class TestScannerConfigAPIRBAC:
    def test_anonymous_and_citizen_denied(self, citizen_client):
        anon_client = APIClient()
        assert anon_client.get("/api/v1/admin-portal/scanner-config/").status_code == 401
        assert anon_client.patch("/api/v1/admin-portal/scanner-config/", {"keyword_cap_points": 50}).status_code == 401
        assert citizen_client.get("/api/v1/admin-portal/scanner-config/").status_code == 403


@pytest.mark.django_db
class TestScannerConfigAPI:
    def test_get_scanner_config(self, admin_client):
        res = admin_client.get("/api/v1/admin-portal/scanner-config/")
        assert res.status_code == 200
        data = res.json()
        assert data["keyword_cap_points"] == 45
        assert data["ip_url_points"] == 25
        assert data["prior_pending_points"] == 20
        assert data["high_priority_threshold"] == 75
        assert data["ruleset_version"] >= 1

    def test_patch_scanner_config_validation_errors(self, admin_client):
        # Value > 100
        res = admin_client.patch(
            "/api/v1/admin-portal/scanner-config/",
            {"keyword_cap_points": 101},
            format="json",
        )
        assert res.status_code == 400

        # Value < 0
        res = admin_client.patch(
            "/api/v1/admin-portal/scanner-config/",
            {"ip_url_points": -1},
            format="json",
        )
        assert res.status_code == 400

        # High priority threshold < 1
        res = admin_client.patch(
            "/api/v1/admin-portal/scanner-config/",
            {"high_priority_threshold": 0},
            format="json",
        )
        assert res.status_code == 400

    def test_patch_scanner_config_bumps_version_and_audits(self, admin_client):
        config, _ = ScannerConfig.objects.get_or_create(id=1, defaults={"ruleset_version": 1})
        initial_version = config.ruleset_version

        res = admin_client.patch(
            "/api/v1/admin-portal/scanner-config/",
            {"keyword_cap_points": 50, "high_priority_threshold": 80},
            format="json",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["keyword_cap_points"] == 50
        assert data["high_priority_threshold"] == 80
        assert data["ruleset_version"] == initial_version + 1

        config.refresh_from_db()
        assert config.ruleset_version == initial_version + 1

        audit = SystemAuditLog.objects.filter(event_type=AuditEventType.CONFIG_CHANGED).latest("occurred_at")
        assert audit.target_type == "CONFIG"
        assert audit.target_id == "1"
        assert audit.metadata["ruleset_version"] == config.ruleset_version
        assert audit.metadata["keyword_cap_points"] == 50
        assert audit.metadata["high_priority_threshold"] == 80
