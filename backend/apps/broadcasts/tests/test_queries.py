import time
from decimal import Decimal

import boto3
import pytest
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from moto import mock_aws
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.broadcasts.models import AdvisorySeverity, AdvisoryStatus, ThreatAdvisory
from apps.core.aws import reset_clients
from apps.core.enums import AudienceGroup
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
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_queries_adv@example.com",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def sns_topic():
    with mock_aws():
        reset_clients()
        sns = boto3.client("sns", region_name="ap-southeast-1")
        resp = sns.create_topic(Name="scamshield-alerts")
        topic_arn = resp["TopicArn"]
        orig_topic = getattr(settings, "ALERTS_TOPIC_ARN", None)
        settings.ALERTS_TOPIC_ARN = topic_arn
        yield topic_arn
        settings.ALERTS_TOPIC_ARN = orig_topic
        reset_clients()


@pytest.mark.django_db
class TestAnalyticsAndAdvisoriesQueryBounds:
    def test_analytics_volume_query_bounds_and_latency(
        self, api_client, analyst_user, django_assert_max_num_queries
    ):
        api_client.force_authenticate(user=analyst_user)
        for i in range(5):
            ScamReport.objects.create(
                reference_code=f"SCM-2026-QB{i:03d}",
                category=ScamCategory.PHISHING,
                platform=Platform.WHATSAPP,
                country_code="MY",
                financial_loss=Decimal("100.00"),
                currency="MYR",
            )

        # First run (cache miss) executes <= 4 queries
        with django_assert_max_num_queries(4):
            res = api_client.get("/api/v1/analytics/volume/")
            assert res.status_code == 200

        # Latency check: warm/cached requests load well under 1 second (< 300ms)
        latencies = []
        for _ in range(5):
            start = time.perf_counter()
            r = api_client.get("/api/v1/analytics/volume/")
            duration = time.perf_counter() - start
            latencies.append(duration)
            assert r.status_code == 200

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 1.0, f"Dashboard load p95={p95:.4f}s exceeded 1s threshold"

    def test_analytics_losses_query_bounds(self, api_client, analyst_user, django_assert_max_num_queries):
        api_client.force_authenticate(user=analyst_user)
        with django_assert_max_num_queries(3):
            res = api_client.get("/api/v1/analytics/losses/")
            assert res.status_code == 200

    def test_analytics_spikes_query_bounds(self, api_client, analyst_user, django_assert_max_num_queries):
        api_client.force_authenticate(user=analyst_user)
        with django_assert_max_num_queries(3):
            res = api_client.get("/api/v1/analytics/spikes/")
            assert res.status_code == 200

    def test_advisories_list_query_bounds(self, api_client, analyst_user, django_assert_max_num_queries):
        now = timezone.now()
        for i in range(3):
            ThreatAdvisory.objects.create(
                title=f"Advisory #{i}",
                body="Warning content",
                severity=AdvisorySeverity.WARNING,
                target_audience="ALL",
                status=AdvisoryStatus.PUBLISHED,
                created_by=analyst_user,
                published_by=analyst_user,
                published_at=now,
            )

        # Public list executes count + select (<= 3 queries)
        with django_assert_max_num_queries(3):
            res = api_client.get("/api/v1/advisories/")
            assert res.status_code == 200

    def test_advisories_create_query_bounds(
        self, api_client, analyst_user, django_assert_max_num_queries
    ):
        api_client.force_authenticate(user=analyst_user)
        payload = {
            "title": "Query Bounds Advisory",
            "body": "Advisory text for query bound testing.",
            "severity": AdvisorySeverity.INFO,
            "target_audience": AudienceGroup.GENERAL,
        }
        with django_assert_max_num_queries(3):
            res = api_client.post("/api/v1/advisories/", payload, format="json")
            assert res.status_code == 201
