import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.scanner.models import HeuristicRule, RuleType, ScannerConfig


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_rules@example.com",
        password="AdminPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def unapproved_admin(db):
    return User.objects.create_user(
        email="unapproved_admin@example.com",
        password="AdminPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.PENDING,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_rules@example.com",
        password="CitizenPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_rules@example.com",
        password="AnalystPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_user(db):
    return User.objects.create_user(
        email="educator_rules@example.com",
        password="EducatorPassword123!",
        role=Role.EDUCATOR,
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
class TestRuleAPIRBAC:
    def test_anonymous_requests_rejected(self):
        client = APIClient()
        res = client.get("/api/v1/admin-portal/rules/")
        assert res.status_code == 401
        res = client.post("/api/v1/admin-portal/rules/", {"rule_type": "KEYWORD", "pattern": "test", "weight": 10})
        assert res.status_code == 401

    def test_non_admin_roles_rejected_with_403(self, citizen_client, analyst_user, educator_user, unapproved_admin):
        # Citizen
        res = citizen_client.get("/api/v1/admin-portal/rules/")
        assert res.status_code == 403

        # Analyst
        client = APIClient()
        client.force_authenticate(user=analyst_user)
        assert client.get("/api/v1/admin-portal/rules/").status_code == 403

        # Educator
        client.force_authenticate(user=educator_user)
        assert client.get("/api/v1/admin-portal/rules/").status_code == 403

        # Unapproved admin
        client.force_authenticate(user=unapproved_admin)
        assert client.get("/api/v1/admin-portal/rules/").status_code == 403

    def test_approved_admin_allowed(self, admin_client):
        res = admin_client.get("/api/v1/admin-portal/rules/")
        assert res.status_code == 200


@pytest.mark.django_db
class TestRuleCRUDAndValidation:
    def test_create_rule_success_and_normalization(self, admin_client):
        payload = {
            "rule_type": "KEYWORD",
            "pattern": "  URGENT_ACTION  ",
            "weight": 15,
            "is_active": True,
        }
        res = admin_client.post("/api/v1/admin-portal/rules/", payload, format="json")
        assert res.status_code == 201
        data = res.json()
        assert data["pattern"] == "urgent_action"
        assert data["weight"] == 15
        assert data["rule_type"] == "KEYWORD"
        assert data["is_active"] is True
        assert "id" in data

    def test_create_rule_validation_errors(self, admin_client):
        # Weight too high
        res = admin_client.post(
            "/api/v1/admin-portal/rules/",
            {"rule_type": "KEYWORD", "pattern": "bad", "weight": 51},
            format="json",
        )
        assert res.status_code == 400
        assert "weight" in res.json()["error"]["details"]

        # Weight too low
        res = admin_client.post(
            "/api/v1/admin-portal/rules/",
            {"rule_type": "KEYWORD", "pattern": "bad", "weight": 0},
            format="json",
        )
        assert res.status_code == 400

        # Blank pattern
        res = admin_client.post(
            "/api/v1/admin-portal/rules/",
            {"rule_type": "KEYWORD", "pattern": "   ", "weight": 10},
            format="json",
        )
        assert res.status_code == 400

        # Invalid rule type
        res = admin_client.post(
            "/api/v1/admin-portal/rules/",
            {"rule_type": "INVALID_TYPE", "pattern": "test", "weight": 10},
            format="json",
        )
        assert res.status_code == 400

    def test_duplicate_rule_returns_409(self, admin_client):
        payload = {"rule_type": "KEYWORD", "pattern": "duplicate", "weight": 10}
        res1 = admin_client.post("/api/v1/admin-portal/rules/", payload, format="json")
        assert res1.status_code == 201

        res2 = admin_client.post("/api/v1/admin-portal/rules/", payload, format="json")
        assert res2.status_code == 409
        assert res2.json()["error"]["code"] == "conflict"

    def test_list_and_filter_rules(self, admin_client, admin_user):
        HeuristicRule.objects.create(rule_type=RuleType.KEYWORD, pattern="k1", weight=10, is_active=True, created_by=admin_user)
        HeuristicRule.objects.create(rule_type=RuleType.TLD, pattern=".xyz", weight=25, is_active=False, created_by=admin_user)

        # Filter by rule_type
        res = admin_client.get("/api/v1/admin-portal/rules/?rule_type=KEYWORD")
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 1
        assert results[0]["pattern"] == "k1"

        # Filter by is_active
        res = admin_client.get("/api/v1/admin-portal/rules/?is_active=false")
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 1
        assert results[0]["pattern"] == ".xyz"

        # Invalid filter value
        res = admin_client.get("/api/v1/admin-portal/rules/?rule_type=UNKNOWN")
        assert res.status_code == 400

    def test_patch_and_delete_rule(self, admin_client, admin_user):
        rule = HeuristicRule.objects.create(
            rule_type=RuleType.KEYWORD,
            pattern="original",
            weight=10,
            is_active=True,
            created_by=admin_user,
        )

        # PATCH
        patch_res = admin_client.patch(
            f"/api/v1/admin-portal/rules/{rule.id}/",
            {"weight": 20, "is_active": False},
            format="json",
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["weight"] == 20
        assert patch_res.json()["is_active"] is False

        # DELETE
        del_res = admin_client.delete(f"/api/v1/admin-portal/rules/{rule.id}/")
        assert del_res.status_code == 204
        assert not HeuristicRule.objects.filter(id=rule.id).exists()


@pytest.mark.django_db
class TestRulesetVersionBumpAndAudit:
    def test_version_bump_and_audit_on_create_patch_delete(self, admin_client):
        config, _ = ScannerConfig.objects.get_or_create(id=1, defaults={"ruleset_version": 1})
        initial_version = config.ruleset_version

        # 1. Create rule -> bumps version
        res_create = admin_client.post(
            "/api/v1/admin-portal/rules/",
            {"rule_type": "KEYWORD", "pattern": "urgent", "weight": 15},
            format="json",
        )
        assert res_create.status_code == 201
        rule_id = res_create.json()["id"]

        config.refresh_from_db()
        assert config.ruleset_version == initial_version + 1

        audit_create = SystemAuditLog.objects.filter(event_type=AuditEventType.RULE_CHANGED).latest("occurred_at")
        assert audit_create.target_type == "RULE"
        assert audit_create.target_id == str(rule_id)
        assert audit_create.metadata["action"] == "created"
        assert audit_create.metadata["ruleset_version"] == config.ruleset_version

        # 2. Patch rule -> bumps version
        res_patch = admin_client.patch(
            f"/api/v1/admin-portal/rules/{rule_id}/",
            {"weight": 30},
            format="json",
        )
        assert res_patch.status_code == 200
        config.refresh_from_db()
        assert config.ruleset_version == initial_version + 2

        audit_patch = SystemAuditLog.objects.filter(event_type=AuditEventType.RULE_CHANGED).latest("occurred_at")
        assert audit_patch.metadata["action"] == "updated"
        assert audit_patch.metadata["ruleset_version"] == config.ruleset_version

        # 3. Delete rule -> bumps version
        res_del = admin_client.delete(f"/api/v1/admin-portal/rules/{rule_id}/")
        assert res_del.status_code == 204
        config.refresh_from_db()
        assert config.ruleset_version == initial_version + 3

        audit_del = SystemAuditLog.objects.filter(event_type=AuditEventType.RULE_CHANGED).latest("occurred_at")
        assert audit_del.metadata["action"] == "deleted"
        assert audit_del.metadata["ruleset_version"] == config.ruleset_version


@pytest.mark.django_db
class TestSeedDefaultRulesCommand:
    def test_seed_command_idempotent(self, admin_user):
        call_command("seed_default_rules")
        count_first = HeuristicRule.objects.count()
        assert count_first > 0

        # Re-run changes nothing
        call_command("seed_default_rules")
        assert HeuristicRule.objects.count() == count_first
