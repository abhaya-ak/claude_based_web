import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.accounts.tests.factories import UserFactory
from apps.ops.models import AuditEventType, SystemAuditLog


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestCitizenRegistration:
    def test_citizen_register_success(self, api_client):
        payload = {
            "email": "Citizen.User@example.com",
            "password": "StrongPassword123!",
            "full_name": "Citizen User",
            "role": "ADMIN",  # Should be ignored per D46
        }
        res = api_client.post("/api/v1/auth/register/", payload, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        assert "user" in res.data
        user_data = res.data["user"]
        assert user_data["email"] == "citizen.user@example.com"
        assert user_data["role"] == Role.CITIZEN
        assert user_data["approval_status"] == ApprovalStatus.APPROVED
        assert "password" not in user_data
        assert "access" not in res.data
        assert settings.REFRESH_COOKIE_NAME not in res.cookies

        # Verify DB
        user = User.objects.get(email="citizen.user@example.com")
        assert user.role == Role.CITIZEN
        assert user.approval_status == ApprovalStatus.APPROVED
        assert user.is_active is True

        # Verify Audit row
        assert SystemAuditLog.objects.filter(
            event_type=AuditEventType.USER_REGISTERED,
            target_type="USER",
            target_id=str(user.id),
        ).exists()

    def test_duplicate_email_returns_409_conflict(self, api_client):
        UserFactory(email="existing@example.com")
        payload = {
            "email": "Existing@Example.com",
            "password": "StrongPassword123!",
            "full_name": "Another User",
        }
        res = api_client.post("/api/v1/auth/register/", payload, format="json")
        assert res.status_code == status.HTTP_409_CONFLICT
        assert res.data["error"]["code"] == "conflict"

    def test_weak_password_returns_400_validation_error(self, api_client):
        payload = {
            "email": "weak@example.com",
            "password": "short",  # Less than 10 characters
            "full_name": "Weak User",
        }
        res = api_client.post("/api/v1/auth/register/", payload, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["error"]["code"] == "validation_error"


@pytest.mark.django_db
class TestStaffRegistration:
    def test_staff_register_success(self, api_client):
        payload = {
            "email": "analyst.new@example.com",
            "password": "StrongPassword123!",
            "full_name": "New Analyst",
            "role": "ANALYST",
            "organization": "National Cyber Agency",
            "credential_note": "Senior Malware Researcher with 8 years experience",
        }
        res = api_client.post("/api/v1/auth/register/staff/", payload, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        assert "message" in res.data
        assert "user" in res.data
        assert res.data["user"]["role"] == Role.ANALYST
        assert res.data["user"]["approval_status"] == ApprovalStatus.PENDING
        assert "access" not in res.data
        assert settings.REFRESH_COOKIE_NAME not in res.cookies

        # Verify DB
        user = User.objects.get(email="analyst.new@example.com")
        assert user.role == Role.ANALYST
        assert user.approval_status == ApprovalStatus.PENDING
        assert user.organization == "National Cyber Agency"
        assert user.credential_note == "Senior Malware Researcher with 8 years experience"

        # Verify Audit row
        assert SystemAuditLog.objects.filter(
            event_type=AuditEventType.STAFF_REGISTERED,
            target_type="USER",
            target_id=str(user.id),
        ).exists()

    def test_staff_register_invalid_role_rejected(self, api_client):
        # CITIZEN and ADMIN roles not permitted on staff registration
        for disallowed_role in ["CITIZEN", "ADMIN", "SUPERUSER"]:
            payload = {
                "email": f"invalid_{disallowed_role.lower()}@example.com",
                "password": "StrongPassword123!",
                "full_name": "Invalid Staff",
                "role": disallowed_role,
                "organization": "Some Org",
                "credential_note": "Note",
            }
            res = api_client.post("/api/v1/auth/register/staff/", payload, format="json")
            assert res.status_code == status.HTTP_400_BAD_REQUEST
            assert res.data["error"]["code"] == "validation_error"

    def test_staff_register_missing_org_or_note_rejected(self, api_client):
        payload = {
            "email": "missing.org@example.com",
            "password": "StrongPassword123!",
            "full_name": "Staff User",
            "role": "EDUCATOR",
            "organization": "",
            "credential_note": "Note",
        }
        res = api_client.post("/api/v1/auth/register/staff/", payload, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

        payload["organization"] = "Some Org"
        payload["credential_note"] = ""
        res = api_client.post("/api/v1/auth/register/staff/", payload, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLoginEndpoint:
    def test_login_success_citizen(self, api_client):
        user = UserFactory(email="citizen.login@example.com", role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        user.set_password("CorrectPassword123!")
        user.save()

        res = api_client.post("/api/v1/auth/login/", {
            "email": "Citizen.Login@example.com",  # Case insensitive
            "password": "CorrectPassword123!",
        }, format="json")

        assert res.status_code == status.HTTP_200_OK
        assert "access" in res.data
        assert res.data["user"]["email"] == "citizen.login@example.com"
        assert res.data["user"]["role"] == Role.CITIZEN

        # Cookie check
        cookie = res.cookies.get(settings.REFRESH_COOKIE_NAME)
        assert cookie is not None
        assert cookie["httponly"] is True
        assert cookie["samesite"].lower() == "lax"
        assert cookie["path"] == "/api/v1/auth/"

        # Audit check: LOGIN_SUCCESS with target USER, id
        assert SystemAuditLog.objects.filter(
            event_type=AuditEventType.LOGIN_SUCCESS,
            target_type="USER",
            target_id=str(user.id),
        ).exists()

    def test_login_enumeration_guard(self, api_client):
        """Unknown email, wrong password, and inactive user return identical 401."""
        user = UserFactory(email="active.user@example.com")
        user.set_password("ValidPassword123!")
        user.save()

        inactive_user = UserFactory(email="inactive.user@example.com", is_active=False)
        inactive_user.set_password("ValidPassword123!")
        inactive_user.save()

        # 1. Unknown email
        res1 = api_client.post("/api/v1/auth/login/", {"email": "unknown@example.com", "password": "wrong"}, format="json")
        # 2. Wrong password
        res2 = api_client.post("/api/v1/auth/login/", {"email": "active.user@example.com", "password": "wrong"}, format="json")
        # 3. Inactive user
        res3 = api_client.post("/api/v1/auth/login/", {"email": "inactive.user@example.com", "password": "ValidPassword123!"}, format="json")

        assert res1.status_code == status.HTTP_401_UNAUTHORIZED
        assert res2.status_code == status.HTTP_401_UNAUTHORIZED
        assert res3.status_code == status.HTTP_401_UNAUTHORIZED

        # Error codes and messages must match identically
        assert res1.data["error"]["code"] == "authentication_failed"
        assert res2.data["error"]["code"] == "authentication_failed"
        assert res3.data["error"]["code"] == "authentication_failed"

        assert res1.data["error"]["message"] == res2.data["error"]["message"] == res3.data["error"]["message"] == "Invalid email or password."

    def test_unapproved_staff_login_returns_403(self, api_client):
        """D45: Staff whose approval_status is not APPROVED returns 403 account_not_approved and NO tokens."""
        for status_val in [ApprovalStatus.PENDING, ApprovalStatus.REJECTED]:
            staff = UserFactory(role=Role.ANALYST, approval_status=status_val)
            staff.set_password("ValidPassword123!")
            staff.save()

            res = api_client.post("/api/v1/auth/login/", {
                "email": staff.email,
                "password": "ValidPassword123!",
            }, format="json")

            assert res.status_code == status.HTTP_403_FORBIDDEN
            assert res.data["error"]["code"] == "account_not_approved"
            assert "access" not in res.data
            assert settings.REFRESH_COOKIE_NAME not in res.cookies


@pytest.mark.django_db
class TestRefreshAndLogoutEndpoints:
    def test_refresh_rotation_and_cookie_reading(self, api_client):
        user = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        user.set_password("Password123!")
        user.save()

        # Login to obtain initial cookie
        login_res = api_client.post("/api/v1/auth/login/", {
            "email": user.email,
            "password": "Password123!",
        }, format="json")
        assert login_res.status_code == status.HTTP_200_OK
        initial_refresh_cookie = login_res.cookies[settings.REFRESH_COOKIE_NAME].value

        # Refresh request without X-Requested-With header fails 403
        api_client.cookies[settings.REFRESH_COOKIE_NAME] = initial_refresh_cookie
        bad_res = api_client.post("/api/v1/auth/refresh/")
        assert bad_res.status_code == status.HTTP_403_FORBIDDEN
        assert bad_res.data["error"]["code"] == "permission_denied"

        # Refresh with header succeeds and rotates
        res = api_client.post("/api/v1/auth/refresh/", HTTP_X_REQUESTED_WITH="scamshield-web")
        assert res.status_code == status.HTTP_200_OK
        assert "access" in res.data
        new_refresh_cookie = res.cookies[settings.REFRESH_COOKIE_NAME].value
        assert new_refresh_cookie != initial_refresh_cookie

        # Reusing the old refresh token fails with 401
        api_client.cookies[settings.REFRESH_COOKIE_NAME] = initial_refresh_cookie
        replay_res = api_client.post("/api/v1/auth/refresh/", HTTP_X_REQUESTED_WITH="scamshield-web")
        assert replay_res.status_code == status.HTTP_401_UNAUTHORIZED
        assert replay_res.data["error"]["code"] == "authentication_failed"

    def test_logout_clears_cookie_always(self, api_client):
        user = UserFactory(role=Role.CITIZEN)
        user.set_password("Password123!")
        user.save()

        login_res = api_client.post("/api/v1/auth/login/", {
            "email": user.email,
            "password": "Password123!",
        }, format="json")
        refresh_cookie = login_res.cookies[settings.REFRESH_COOKIE_NAME].value

        # Missing header fails with 403
        api_client.cookies[settings.REFRESH_COOKIE_NAME] = refresh_cookie
        bad_res = api_client.post("/api/v1/auth/logout/")
        assert bad_res.status_code == status.HTTP_403_FORBIDDEN

        # Logout with header returns 204 and clears cookie
        res = api_client.post("/api/v1/auth/logout/", HTTP_X_REQUESTED_WITH="scamshield-web")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert res.cookies[settings.REFRESH_COOKIE_NAME].value == ""
        assert int(res.cookies[settings.REFRESH_COOKIE_NAME]["max-age"]) == 0

        # Repeated logout with empty or garbage cookie still returns 204
        api_client.cookies[settings.REFRESH_COOKIE_NAME] = "garbage-token"
        res_repeat = api_client.post("/api/v1/auth/logout/", HTTP_X_REQUESTED_WITH="scamshield-web")
        assert res_repeat.status_code == status.HTTP_204_NO_CONTENT
        assert res_repeat.cookies[settings.REFRESH_COOKIE_NAME].value == ""
