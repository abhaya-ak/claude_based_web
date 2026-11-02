import boto3
import pytest
from django.conf import settings
from moto import mock_aws
from rest_framework.test import APIClient

from apps.core.aws import reset_clients
from apps.core.enums import AudienceGroup


@pytest.fixture
def api_client():
    return APIClient()


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
class TestAlertSubscriptionQueryCounts:
    def test_subscription_creation_query_count(self, api_client, sns_topic, django_assert_max_num_queries):
        payload = {
            "channel": "EMAIL",
            "endpoint": "query_test@example.com",
            "audience": AudienceGroup.GENERAL,
        }

        with django_assert_max_num_queries(3):
            res = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
            assert res.status_code == 201

    def test_subscription_confirmation_query_count(self, api_client, sns_topic, django_assert_max_num_queries):
        payload = {
            "channel": "EMAIL",
            "endpoint": "query_confirm@example.com",
            "audience": AudienceGroup.GENERAL,
        }
        res = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
        token = res.data["token"]

        with django_assert_max_num_queries(2):
            confirm_res = api_client.post(
                "/api/v1/alerts/subscriptions/confirm/",
                {"token": token},
                format="json",
            )
            assert confirm_res.status_code == 200
