import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import ApprovalStatus, Role
from apps.accounts.tests.factories import UserFactory
from apps.ops.models import AuditEventType, SystemAuditLog


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestCurrentUserEndpoint:
    def test_get_me_authenticated(self, api_client):
        user = UserFactory(
            role=Role.ANALYST,
            approval_status=ApprovalStatus.APPROVED,
            organization="Cyber Security Agency",
        )
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        res = api_client.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert data["id"] == str(user.id)
        assert data["email"] == user.email
        assert data["full_name"] == user.full_name
        assert data["role"] == Role.ANALYST
        assert data["approval_status"] == ApprovalStatus.APPROVED
        assert data["organization"] == "Cyber Security Agency"
        assert "created_at" in data
        assert "password" not in data

    def test_get_me_unauthenticated_returns_401(self, api_client):
        res = api_client.get("/api/v1/auth/me/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["error"]["code"] in ("not_authenticated", "authentication_failed")

    def test_get_me_deactivated_user_token_rejected(self, api_client):
        user = UserFactory(is_active=True)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Deactivate user after token issuance
        user.is_active = False
        user.save()

        res = api_client.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["error"]["code"] == "authentication_failed"

    def test_get_me_unapproved_staff_token_rejected(self, api_client):
        user = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.APPROVED)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Unapprove user after token issuance
        user.approval_status = ApprovalStatus.REJECTED
        user.save()

        res = api_client.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert res.data["error"]["code"] == "account_not_approved"


@pytest.mark.django_db
class TestPasswordChangeEndpoint:
    def test_password_change_success_and_revocation(self, api_client):
        user = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        user.set_password("OldPassword123!")
        user.save()

        # Simulate two active sessions (two refresh tokens)
        session1_refresh = RefreshToken.for_user(user)
        session2_refresh = RefreshToken.for_user(user)
        access_token = str(session1_refresh.access_token)

        payload = {
            "current_password": "OldPassword123!",
            "new_password": "NewStrongPassword456!",
        }
        res = api_client.post(
            "/api/v1/auth/password/change/",
            payload,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        assert res.status_code == status.HTTP_204_NO_CONTENT
        # Cookie must be cleared
        assert res.cookies[settings.REFRESH_COOKIE_NAME].value == ""
        assert int(res.cookies[settings.REFRESH_COOKIE_NAME]["max-age"]) == 0

        # Verify password actually updated
        user.refresh_from_db()
        assert user.check_password("NewStrongPassword456!") is True
        assert user.check_password("OldPassword123!") is False

        # Verify Audit row
        assert SystemAuditLog.objects.filter(
            event_type=AuditEventType.PASSWORD_CHANGED,
            actor=user,
            target_type="USER",
            target_id=str(user.id),
        ).exists()

        # Verify ALL outstanding refresh tokens for that user are blacklisted
        api_client.cookies[settings.REFRESH_COOKIE_NAME] = str(session1_refresh)
        res_refresh1 = api_client.post("/api/v1/auth/refresh/", HTTP_X_REQUESTED_WITH="scamshield-web")
        assert res_refresh1.status_code == status.HTTP_401_UNAUTHORIZED

        api_client.cookies[settings.REFRESH_COOKIE_NAME] = str(session2_refresh)
        res_refresh2 = api_client.post("/api/v1/auth/refresh/", HTTP_X_REQUESTED_WITH="scamshield-web")
        assert res_refresh2.status_code == status.HTTP_401_UNAUTHORIZED

    def test_password_change_wrong_current_password(self, api_client):
        user = UserFactory()
        user.set_password("CorrectOldPassword123!")
        user.save()

        refresh = RefreshToken.for_user(user)
        res = api_client.post(
            "/api/v1/auth/password/change/",
            {
                "current_password": "WrongPassword123!",
                "new_password": "NewValidPassword456!",
            },
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["error"]["code"] == "validation_error"

    def test_password_change_weak_new_password(self, api_client):
        user = UserFactory()
        user.set_password("CorrectOldPassword123!")
        user.save()

        refresh = RefreshToken.for_user(user)
        res = api_client.post(
            "/api/v1/auth/password/change/",
            {
                "current_password": "CorrectOldPassword123!",
                "new_password": "short",  # Less than 10 chars
            },
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["error"]["code"] == "validation_error"
