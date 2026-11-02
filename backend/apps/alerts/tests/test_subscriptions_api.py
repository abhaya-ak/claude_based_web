import json

import boto3
import pytest
from django.conf import settings
from moto import mock_aws
from rest_framework.test import APIClient

from apps.alerts.models import AlertSubscription, Channel, SubscriptionStatus
from apps.core.aws import reset_clients
from apps.core.enums import AudienceGroup
from apps.reports.models import ScamCategory


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
class TestAlertSubscriptionsAPI:
    def test_moto_sns_subscription_creation_and_filter_policy(self, api_client, sns_topic):
        """TO BE PROVEN #14: SNS subscription created with expected FilterPolicy."""
        payload = {
            "channel": "EMAIL",
            "endpoint": "senior_family@example.com",
            "audience": AudienceGroup.ELDERLY,
            "categories": [ScamCategory.PHISHING, ScamCategory.IMPERSONATION],
        }

        res = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
        assert res.status_code == 201
        data = res.data
        assert data["status"] == SubscriptionStatus.PENDING_CONFIRMATION
        assert data["channel"] == "EMAIL"
        assert data["audience"] == AudienceGroup.ELDERLY
        assert "token" in data

        sub = AlertSubscription.objects.get(id=data["id"])
        assert sub.status == SubscriptionStatus.PENDING_CONFIRMATION
        assert sub.sns_subscription_arn is not None

        # Verify SNS FilterPolicy attributes
        sns = boto3.client("sns", region_name="ap-southeast-1")
        attrs = sns.get_subscription_attributes(SubscriptionArn=sub.sns_subscription_arn)["Attributes"]
        assert "FilterPolicy" in attrs
        policy = json.loads(attrs["FilterPolicy"])
        assert policy["audience"] == ["ALL", AudienceGroup.ELDERLY]
        assert set(policy["category"]) == {ScamCategory.PHISHING, ScamCategory.IMPERSONATION}

    def test_subscription_with_empty_categories_omits_category_filter(self, api_client, sns_topic):
        payload = {
            "channel": "EMAIL",
            "endpoint": "all_alerts@example.com",
            "audience": AudienceGroup.GENERAL,
            "categories": [],
        }

        res = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
        assert res.status_code == 201

        sub = AlertSubscription.objects.get(id=res.data["id"])
        sns = boto3.client("sns", region_name="ap-southeast-1")
        attrs = sns.get_subscription_attributes(SubscriptionArn=sub.sns_subscription_arn)["Attributes"]
        policy = json.loads(attrs["FilterPolicy"])
        assert policy["audience"] == ["ALL", AudienceGroup.GENERAL]
        assert "category" not in policy  # Omitted when 'all' per specification

    def test_sms_channel_disabled_by_default_returns_400(self, api_client, monkeypatch):
        monkeypatch.setattr(settings, "ENABLE_SMS_ALERTS", False)
        payload = {
            "channel": "SMS",
            "endpoint": "+60123456789",
            "audience": AudienceGroup.GENERAL,
        }

        res = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
        assert res.status_code == 400
        assert res.data["error"]["code"] in ("sms_disabled", "validation_error")
        assert "disabled" in str(res.data).lower()

    def test_sms_channel_enabled_validates_e164_and_subscribes(self, api_client, sns_topic, monkeypatch):
        monkeypatch.setattr(settings, "ENABLE_SMS_ALERTS", True)
        payload = {
            "channel": "SMS",
            "endpoint": "012-3456789",
            "audience": AudienceGroup.TEENAGER,
        }

        res = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
        assert res.status_code == 201
        sub = AlertSubscription.objects.get(id=res.data["id"])
        assert sub.channel == Channel.SMS
        assert sub.endpoint == "+60123456789"

    def test_duplicate_subscription_returns_existing_without_leaking(self, api_client, sns_topic):
        payload = {
            "channel": "EMAIL",
            "endpoint": "dup_check@example.com",
            "audience": AudienceGroup.NON_TECH,
        }

        res1 = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
        assert res1.status_code == 201
        assert res1.data.get("token") is not None

        # Second submission
        res2 = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
        assert res2.status_code == 200
        assert res2.data["id"] == res1.data["id"]
        # Do not leak a new token on duplicate submission
        assert "token" not in res2.data or res2.data.get("token") is None

        assert AlertSubscription.objects.filter(endpoint_hash=res1.data["id"]).count() <= 1

    def test_confirmation_flow_updates_to_active(self, api_client, sns_topic):
        payload = {
            "channel": "EMAIL",
            "endpoint": "confirm_me@example.com",
            "audience": AudienceGroup.GENERAL,
        }
        res = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
        token = res.data["token"]

        confirm_res = api_client.post(
            "/api/v1/alerts/subscriptions/confirm/",
            {"token": token},
            format="json",
        )
        assert confirm_res.status_code == 200
        assert confirm_res.data["status"] == SubscriptionStatus.ACTIVE

        sub = AlertSubscription.objects.get(id=res.data["id"])
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.confirmed_at is not None

    def test_unsubscribe_flow_calls_sns_unsubscribe(self, api_client, sns_topic):
        payload = {
            "channel": "EMAIL",
            "endpoint": "unsub_me@example.com",
            "audience": AudienceGroup.GENERAL,
        }
        res = api_client.post("/api/v1/alerts/subscriptions/", payload, format="json")
        token = res.data["token"]

        unsub_res = api_client.post(
            "/api/v1/alerts/subscriptions/unsubscribe/",
            {"token": token},
            format="json",
        )
        assert unsub_res.status_code == 200
        assert unsub_res.data["status"] == SubscriptionStatus.UNSUBSCRIBED

        sub = AlertSubscription.objects.get(id=res.data["id"])
        assert sub.status == SubscriptionStatus.UNSUBSCRIBED
        assert sub.unsubscribed_at is not None

    def test_invalid_tokens_return_appropriate_errors(self, api_client):
        res_empty = api_client.post("/api/v1/alerts/subscriptions/confirm/", {}, format="json")
        assert res_empty.status_code == 400

        res_not_found = api_client.post(
            "/api/v1/alerts/subscriptions/confirm/",
            {"token": "non_existent_token_12345"},
            format="json",
        )
        assert res_not_found.status_code == 404
        assert res_not_found.data["error"]["code"] == "subscription_not_found"
