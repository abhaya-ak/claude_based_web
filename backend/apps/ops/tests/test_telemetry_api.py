from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="ops_admin@scamshield.test",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="ops_analyst@scamshield.test",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="ops_citizen@scamshield.test",
        password="ValidPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestTelemetryApi:
    def test_anonymous_rejected_401(self):
        client = APIClient()
        res = client.get("/api/v1/admin-portal/telemetry/metrics/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_admin_forbidden_403(self, analyst_user, citizen_user):
        for user in [analyst_user, citizen_user]:
            client = APIClient()
            client.force_authenticate(user=user)
            res = client.get("/api/v1/admin-portal/telemetry/metrics/")
            assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_success_default_range(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)

        with patch("apps.ops.services.cloudwatch_service.get_dashboard_series") as mock_series:
            mock_series.return_value = {
                "time_range": "24h",
                "period": 300,
                "degraded": False,
                "infrastructure": {},
                "operations": {},
            }
            res = client.get("/api/v1/admin-portal/telemetry/metrics/")
            assert res.status_code == status.HTTP_200_OK
            assert res.json()["time_range"] == "24h"
            assert "max-age=60" in res.headers.get("Cache-Control", "")
            mock_series.assert_called_once_with(time_range="24h")

    @pytest.mark.parametrize("valid_range", ["1h", "6h", "24h", "7d"])
    def test_admin_success_valid_ranges(self, admin_user, valid_range):
        client = APIClient()
        client.force_authenticate(user=admin_user)

        with patch("apps.ops.services.cloudwatch_service.get_dashboard_series") as mock_series:
            mock_series.return_value = {
                "time_range": valid_range,
                "period": 300,
                "degraded": False,
                "infrastructure": {},
                "operations": {},
            }
            res = client.get(f"/api/v1/admin-portal/telemetry/metrics/?range={valid_range}")
            assert res.status_code == status.HTTP_200_OK
            mock_series.assert_called_once_with(time_range=valid_range)

    def test_invalid_range_returns_400(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)
        res = client.get("/api/v1/admin-portal/telemetry/metrics/?range=99d")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "range" in str(res.json())
