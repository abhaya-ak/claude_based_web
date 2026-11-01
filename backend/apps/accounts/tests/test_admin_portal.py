import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import ApprovalStatus, Role, User
from apps.accounts.tests.factories import UserFactory
from apps.ops.models import AuditEventType, SystemAuditLog


@pytest.fixture
def api_client():
    return APIClient()


def auth_header_for(user):
    refresh = RefreshToken.for_user(user)
    return f"Bearer {refresh.access_token}"


@pytest.mark.django_db
class TestAdminPortalPermissions:
    def test_non_admin_roles_rejected_on_all_endpoints(self, api_client):
        target = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.PENDING)
        endpoints = [
            ("get", "/api/v1/admin-portal/users/", None),
            ("post", f"/api/v1/admin-portal/users/{target.id}/approve/", {}),
            ("post", f"/api/v1/admin-portal/users/{target.id}/reject/", {"reason": "Not qualified"}),
            ("post", f"/api/v1/admin-portal/users/{target.id}/change-role/", {"role": "CITIZEN"}),
        ]

        # 1. Anonymous -> 401
        for method, url, data in endpoints:
            if method == "get":
                res = api_client.get(url)
            else:
                res = api_client.post(url, data, format="json")
            assert res.status_code == status.HTTP_401_UNAUTHORIZED, f"{url} allowed anonymous"
            assert res.data["error"]["code"] in ("not_authenticated", "authentication_failed")

        # 2. Citizen, Analyst, Educator -> 403
        for role_val in [Role.CITIZEN, Role.ANALYST, Role.EDUCATOR]:
            user = UserFactory(role=role_val, approval_status=ApprovalStatus.APPROVED)
            auth = auth_header_for(user)
            for method, url, data in endpoints:
                if method == "get":
                    res = api_client.get(url, HTTP_AUTHORIZATION=auth)
                else:
                    res = api_client.post(url, data, format="json", HTTP_AUTHORIZATION=auth)
                assert res.status_code == status.HTTP_403_FORBIDDEN, f"{url} allowed role {role_val}"
                assert res.data["error"]["code"] == "permission_denied"


@pytest.mark.django_db
class TestAdminUserList:
    def test_list_users_and_status_filtering(self, api_client):
        admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        auth = auth_header_for(admin)

        # Create distinct users
        UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.PENDING)
        UserFactory(role=Role.EDUCATOR, approval_status=ApprovalStatus.REJECTED)

        # 1. All users
        res = api_client.get("/api/v1/admin-portal/users/", HTTP_AUTHORIZATION=auth)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) >= 4

        # 2. Filter by status=PENDING
        res_pending = api_client.get("/api/v1/admin-portal/users/?status=PENDING", HTTP_AUTHORIZATION=auth)
        assert res_pending.status_code == status.HTTP_200_OK
        for u in res_pending.data:
            assert u["approval_status"] == ApprovalStatus.PENDING

        # 3. Invalid status -> 400 validation_error
        res_invalid = api_client.get("/api/v1/admin-portal/users/?status=INVALID_STATUS", HTTP_AUTHORIZATION=auth)
        assert res_invalid.status_code == status.HTTP_400_BAD_REQUEST
        assert res_invalid.data["error"]["code"] == "validation_error"

    def test_list_users_constant_query_count(self, api_client, django_assert_num_queries):
        admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        auth = auth_header_for(admin)

        # Seed 6 users with approved_by relationships
        for _ in range(6):
            UserFactory(
                role=Role.ANALYST,
                approval_status=ApprovalStatus.APPROVED,
                approved_by=admin,
            )

        # Auth + ScamShieldJWTAuthentication user lookup + 1 query for User list (select_related approved_by)
        with django_assert_num_queries(2):
            res = api_client.get("/api/v1/admin-portal/users/", HTTP_AUTHORIZATION=auth)
            assert res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestAdminApproveWorkflow:
    def test_approve_pending_staff_user(self, api_client):
        admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        auth = auth_header_for(admin)

        analyst = UserFactory(
            email="pending.analyst@example.com",
            role=Role.ANALYST,
            approval_status=ApprovalStatus.PENDING,
        )
        analyst.set_password("SecurePassword123!")
        analyst.save()

        # Approve endpoint
        res = api_client.post(
            f"/api/v1/admin-portal/users/{analyst.id}/approve/",
            {},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert data["id"] == str(analyst.id)
        assert data["approval_status"] == ApprovalStatus.APPROVED
        assert data["approved_by"] == str(admin.id)
        assert data["approved_at"] is not None

        # Verify DB
        analyst.refresh_from_db()
        assert analyst.approval_status == ApprovalStatus.APPROVED
        assert analyst.approved_by == admin
        assert analyst.approved_at is not None

        # Verify audit row
        assert SystemAuditLog.objects.filter(
            event_type=AuditEventType.ROLE_APPROVED,
            actor=admin,
            target_type="USER",
            target_id=str(analyst.id),
        ).exists()

        # The approved analyst can now log in successfully!
        login_res = api_client.post("/api/v1/auth/login/", {
            "email": "pending.analyst@example.com",
            "password": "SecurePassword123!",
        }, format="json")
        assert login_res.status_code == status.HTTP_200_OK

    def test_approve_already_approved_or_rejected_conflict(self, api_client):
        admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        auth = auth_header_for(admin)

        approved_user = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.APPROVED)
        res1 = api_client.post(
            f"/api/v1/admin-portal/users/{approved_user.id}/approve/",
            {},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
        assert res1.status_code == status.HTTP_409_CONFLICT
        assert res1.data["error"]["code"] == "conflict"

        rejected_user = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.REJECTED)
        res2 = api_client.post(
            f"/api/v1/admin-portal/users/{rejected_user.id}/approve/",
            {},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
        assert res2.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
class TestAdminRejectWorkflow:
    def test_reject_pending_staff_user(self, api_client):
        admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        auth = auth_header_for(admin)

        educator = UserFactory(
            email="pending.educator@example.com",
            role=Role.EDUCATOR,
            approval_status=ApprovalStatus.PENDING,
        )
        educator.set_password("SecurePassword123!")
        educator.save()

        # 1. Missing reason -> 400
        bad_res = api_client.post(
            f"/api/v1/admin-portal/users/{educator.id}/reject/",
            {"reason": ""},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
        assert bad_res.status_code == status.HTTP_400_BAD_REQUEST
        assert bad_res.data["error"]["code"] == "validation_error"

        # 2. Valid rejection with reason
        res = api_client.post(
            f"/api/v1/admin-portal/users/{educator.id}/reject/",
            {"reason": "Insufficient credentials provided."},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["approval_status"] == ApprovalStatus.REJECTED
        assert res.data["rejection_reason"] == "Insufficient credentials provided."

        # Verify DB
        educator.refresh_from_db()
        assert educator.approval_status == ApprovalStatus.REJECTED
        assert educator.rejection_reason == "Insufficient credentials provided."

        # Verify audit row
        assert SystemAuditLog.objects.filter(
            event_type=AuditEventType.ROLE_REJECTED,
            actor=admin,
            target_type="USER",
            target_id=str(educator.id),
        ).exists()

        # Login fails with 403 account_not_approved
        login_res = api_client.post("/api/v1/auth/login/", {
            "email": "pending.educator@example.com",
            "password": "SecurePassword123!",
        }, format="json")
        assert login_res.status_code == status.HTTP_403_FORBIDDEN
        assert login_res.data["error"]["code"] == "account_not_approved"

    def test_reject_non_pending_returns_409_conflict(self, api_client):
        admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        auth = auth_header_for(admin)

        citizen = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        res = api_client.post(
            f"/api/v1/admin-portal/users/{citizen.id}/reject/",
            {"reason": "Invalid user"},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
        assert res.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
class TestAdminChangeRoleWorkflow:
    def test_change_role_success(self, api_client):
        admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        auth = auth_header_for(admin)

        citizen = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        res = api_client.post(
            f"/api/v1/admin-portal/users/{citizen.id}/change-role/",
            {"role": Role.ANALYST},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["role"] == Role.ANALYST
        assert res.data["approval_status"] == ApprovalStatus.APPROVED

        citizen.refresh_from_db()
        assert citizen.role == Role.ANALYST
        assert citizen.approval_status == ApprovalStatus.APPROVED

        # Verify audit row
        assert SystemAuditLog.objects.filter(
            event_type=AuditEventType.ROLE_CHANGED,
            actor=admin,
            target_type="USER",
            target_id=str(citizen.id),
        ).exists()

    def test_admin_cannot_change_own_role(self, api_client):
        admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        auth = auth_header_for(admin)

        res = api_client.post(
            f"/api/v1/admin-portal/users/{admin.id}/change-role/",
            {"role": Role.CITIZEN},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
        assert res.status_code == status.HTTP_409_CONFLICT
        assert res.data["error"]["code"] == "conflict"

    def test_last_active_admin_protection(self, api_client):
        # Only 1 active admin exists in system
        User.objects.filter(role=Role.ADMIN).delete()
        admin1 = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED, is_active=True)
        auth1 = auth_header_for(admin1)

        # Another admin attempts to be demoted - but admin1 is the only one
        res = api_client.post(
            f"/api/v1/admin-portal/users/{admin1.id}/change-role/",
            {"role": Role.CITIZEN},
            format="json",
            HTTP_AUTHORIZATION=auth1,
        )
        assert res.status_code == status.HTTP_409_CONFLICT

        # Create a second active admin
        admin2 = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED, is_active=True)
        auth2 = auth_header_for(admin2)

        # Now admin2 can demote admin1 because admin2 remains active approved admin
        res_allowed = api_client.post(
            f"/api/v1/admin-portal/users/{admin1.id}/change-role/",
            {"role": Role.CITIZEN},
            format="json",
            HTTP_AUTHORIZATION=auth2,
        )
        assert res_allowed.status_code == status.HTTP_200_OK
        assert res_allowed.data["role"] == Role.CITIZEN

        # Trying to demote admin2 now fails because admin2 is now the last admin
        res_fail_last = api_client.post(
            f"/api/v1/admin-portal/users/{admin2.id}/change-role/",
            {"role": Role.CITIZEN},
            format="json",
            HTTP_AUTHORIZATION=auth2,
        )
        assert res_fail_last.status_code == status.HTTP_409_CONFLICT
