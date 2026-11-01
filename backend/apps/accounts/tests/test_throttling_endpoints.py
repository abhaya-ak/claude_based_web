import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.ops.models import AuditEventType, SystemAuditLog


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestEndpointThrottling:
    def test_login_failure_throttle_boundaries(self, api_client):
        user = UserFactory(email="victim@example.com")
        user.set_password("Secret12345!")
        user.save()

        # 10 failed login attempts from client IP
        for _attempt in range(1, 11):
            res = api_client.post(
                "/api/v1/auth/login/",
                {"email": user.email, "password": "WrongPassword!"},
                format="json",
                REMOTE_ADDR="198.51.100.1",
            )
            assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # 11th failed login attempt is blocked with 429
        res_blocked = api_client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "WrongPassword!"},
            format="json",
            REMOTE_ADDR="198.51.100.1",
        )
        assert res_blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert res_blocked.data["error"]["code"] == "throttled"
        assert "Retry-After" in res_blocked.headers

        # Verify RATE_LIMIT_BLOCK audit row
        assert SystemAuditLog.objects.filter(event_type=AuditEventType.RATE_LIMIT_BLOCK).exists()

        # Attacker from a different IP targeting the same user account is also blocked (per-account limit)
        res_other_ip_same_user = api_client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "WrongPassword!"},
            format="json",
            REMOTE_ADDR="198.51.100.2",
        )
        assert res_other_ip_same_user.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # Different user login from the other IP is unaffected
        other_user = UserFactory(email="unaffected@example.com")
        other_user.set_password("Secret12345!")
        other_user.save()
        res_other_user = api_client.post(
            "/api/v1/auth/login/",
            {"email": other_user.email, "password": "Secret12345!"},
            format="json",
            REMOTE_ADDR="198.51.100.2",
        )
        assert res_other_user.status_code == status.HTTP_200_OK

    def test_registration_throttle_boundaries(self, api_client):
        # 10 registrations from same IP
        for i in range(1, 11):
            res = api_client.post(
                "/api/v1/auth/register/",
                {
                    "email": f"citizen_{i}@example.com",
                    "password": "Password123!",
                    "full_name": f"User {i}",
                },
                format="json",
                REMOTE_ADDR="198.51.100.5",
            )
            assert res.status_code == status.HTTP_201_CREATED

        # 11th registration attempt from same IP is throttled
        res_blocked = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "citizen_11@example.com",
                "password": "Password123!",
                "full_name": "User 11",
            },
            format="json",
            REMOTE_ADDR="198.51.100.5",
        )
        assert res_blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert res_blocked.data["error"]["code"] == "throttled"
        assert res_blocked.headers.get("Retry-After") == "3600"

        # Another IP is unaffected
        res_other_ip = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "citizen_other_ip@example.com",
                "password": "Password123!",
                "full_name": "User Other",
            },
            format="json",
            REMOTE_ADDR="198.51.100.6",
        )
        assert res_other_ip.status_code == status.HTTP_201_CREATED
