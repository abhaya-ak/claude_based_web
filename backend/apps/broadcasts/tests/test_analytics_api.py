from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.reports.models import Platform, ScamCategory, ScamReport


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_analytics@example.com",
        password="ValidPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_user(db):
    return User.objects.create_user(
        email="educator_analytics@example.com",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def analyst_pending(db):
    return User.objects.create_user(
        email="analyst_pending_analytics@example.com",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.PENDING,
    )


@pytest.fixture
def analyst_approved(db):
    return User.objects.create_user(
        email="analyst_approved_analytics@example.com",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_approved(db):
    return User.objects.create_user(
        email="admin_approved_analytics@example.com",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestAnalyticsRBAC:
    ENDPOINTS = [
        "/api/v1/analytics/volume/",
        "/api/v1/analytics/losses/",
        "/api/v1/analytics/tactics/",
        "/api/v1/analytics/spikes/",
    ]

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_anonymous_access_returns_401(self, api_client, endpoint):
        res = api_client.get(endpoint)
        assert res.status_code == 401
        assert res.data["error"]["code"] in {"not_authenticated", "authentication_failed"}

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_citizen_access_returns_403(self, api_client, citizen_user, endpoint):
        api_client.force_authenticate(user=citizen_user)
        res = api_client.get(endpoint)
        assert res.status_code == 403
        assert res.data["error"]["code"] == "permission_denied"

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_educator_access_returns_403(self, api_client, educator_user, endpoint):
        api_client.force_authenticate(user=educator_user)
        res = api_client.get(endpoint)
        assert res.status_code == 403
        assert res.data["error"]["code"] == "permission_denied"

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_pending_analyst_access_returns_403(self, api_client, analyst_pending, endpoint):
        api_client.force_authenticate(user=analyst_pending)
        res = api_client.get(endpoint)
        assert res.status_code == 403
        assert res.data["error"]["code"] == "permission_denied"

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_approved_analyst_access_returns_200(self, api_client, analyst_approved, endpoint):
        api_client.force_authenticate(user=analyst_approved)
        res = api_client.get(endpoint)
        assert res.status_code == 200

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_approved_admin_access_returns_200(self, api_client, admin_approved, endpoint):
        api_client.force_authenticate(user=admin_approved)
        res = api_client.get(endpoint)
        assert res.status_code == 200


@pytest.mark.django_db
class TestAnalyticsDateRangeValidation:
    def test_date_range_start_after_end_returns_400(self, api_client, analyst_approved):
        api_client.force_authenticate(user=analyst_approved)
        res = api_client.get("/api/v1/analytics/volume/?start_date=2026-10-15&end_date=2026-10-01")
        assert res.status_code == 400
        assert res.data["error"]["code"] in {"invalid_date_range", "validation_error"}

    def test_date_range_exceeding_90_days_returns_400(self, api_client, analyst_approved):
        api_client.force_authenticate(user=analyst_approved)
        res = api_client.get("/api/v1/analytics/losses/?start_date=2026-01-01&end_date=2026-04-15")
        assert res.status_code == 400
        assert res.data["error"]["code"] in {"date_range_too_large", "validation_error"}

    def test_invalid_date_format_returns_400(self, api_client, analyst_approved):
        api_client.force_authenticate(user=analyst_approved)
        res = api_client.get("/api/v1/analytics/tactics/?start_date=not-a-date&end_date=2026-10-01")
        assert res.status_code == 400
        assert res.data["error"]["code"] in {"invalid_date", "validation_error"}

    def test_exactly_90_days_returns_200(self, api_client, analyst_approved):
        api_client.force_authenticate(user=analyst_approved)
        start = date(2026, 6, 1)
        end = start + timedelta(days=90)
        res = api_client.get(f"/api/v1/analytics/volume/?start_date={start}&end_date={end}")
        assert res.status_code == 200

    def test_default_trailing_30_days_returns_200(self, api_client, analyst_approved):
        api_client.force_authenticate(user=analyst_approved)
        res = api_client.get("/api/v1/analytics/volume/")
        assert res.status_code == 200


@pytest.mark.django_db
class TestAnalyticsCachingAndPrivacy:
    def test_response_cached_for_60s_and_sets_header(self, api_client, analyst_approved, django_assert_num_queries):
        api_client.force_authenticate(user=analyst_approved)
        ScamReport.objects.create(
            reference_code="SCM-2026-CACHE01",
            category=ScamCategory.PHISHING,
            platform=Platform.WHATSAPP,
            country_code="MY",
            financial_loss=Decimal("500.00"),
            currency="MYR",
        )

        # First request populates cache
        res1 = api_client.get("/api/v1/analytics/volume/?start_date=2026-10-01&end_date=2026-10-15")
        assert res1.status_code == 200
        assert res1.headers.get("Cache-Control") == "private, max-age=60"

        # Second request hits cache: 0 DB queries to reports table
        with django_assert_num_queries(0):
            res2 = api_client.get("/api/v1/analytics/volume/?start_date=2026-10-01&end_date=2026-10-15")
            assert res2.status_code == 200
            assert res2.data == res1.data
            assert res2.headers.get("Cache-Control") == "private, max-age=60"

    def test_privacy_no_pii_or_report_identifiers(self, api_client, analyst_approved):
        api_client.force_authenticate(user=analyst_approved)
        report = ScamReport.objects.create(
            reference_code="SCM-2026-PRIV999",
            category=ScamCategory.IMPERSONATION,
            platform=Platform.TELEGRAM,
            country_code="MY",
            message_text="Victim secret message text that must NEVER leak into analytics",
            financial_loss=Decimal("12000.00"),
            currency="MYR",
        )

        for path in [
            "/api/v1/analytics/volume/",
            "/api/v1/analytics/losses/",
            "/api/v1/analytics/tactics/",
            "/api/v1/analytics/spikes/",
        ]:
            res = api_client.get(path)
            assert res.status_code == 200
            body_str = str(res.data)
            assert str(report.id) not in body_str
            assert report.reference_code not in body_str
            assert "Victim secret message" not in body_str
