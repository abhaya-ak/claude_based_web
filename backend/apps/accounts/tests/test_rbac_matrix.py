import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role
from apps.accounts.tests.factories import UserFactory


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
