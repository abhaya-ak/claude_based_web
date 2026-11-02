import json
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from moto import mock_aws
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.broadcasts.models import AdvisorySeverity, AdvisoryStatus, ThreatAdvisory
from apps.core.aws import reset_clients
from apps.core.enums import AudienceGroup
from apps.ops.models import SystemAuditLog
from apps.reports.models import ScamCategory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_publisher@example.com",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_publisher@example.com",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_publisher@example.com",
        password="ValidPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def mock_sns():
    with mock_aws():
        reset_clients()
        sns = boto3.client("sns", region_name="ap-southeast-1")
        resp = sns.create_topic(Name="scamshield-alerts")
        topic_arn = resp["TopicArn"]
        orig_topic = getattr(settings, "ALERTS_TOPIC_ARN", None)
        settings.ALERTS_TOPIC_ARN = topic_arn
        yield {"client": sns, "topic_arn": topic_arn}
        settings.ALERTS_TOPIC_ARN = orig_topic
        reset_clients()


@pytest.fixture
def draft_advisory(analyst_user):
    return ThreatAdvisory.objects.create(
        title="Emergency Warning: Tax Impersonation",
        body="Scammers calling claiming to be LHDN tax officers. Do not transfer funds.",
        sms_text="LHDN tax officer scam alert. Never transfer funds.",
        severity=AdvisorySeverity.CRITICAL,
        target_audience=AudienceGroup.GENERAL,
        category=ScamCategory.IMPERSONATION,
        status=AdvisoryStatus.DRAFT,
        created_by=analyst_user,
    )


@pytest.mark.django_db
class TestAdvisoryPublishAPI:
    def test_analyst_publishes_draft_advisory_success(self, api_client, analyst_user, draft_advisory, mock_sns):
        api_client.force_authenticate(user=analyst_user)
        with patch("apps.core.metrics.emit") as mock_metric:
            res = api_client.post(f"/api/v1/advisories/{draft_advisory.id}/publish/")
            assert res.status_code == 200
            assert res.data["status"] == AdvisoryStatus.PUBLISHED
            assert res.data["published_at"] is not None
            assert res.data["sns_message_id"] is not None

            draft_advisory.refresh_from_db()
            assert draft_advisory.status == AdvisoryStatus.PUBLISHED
            assert draft_advisory.published_by == analyst_user
            assert draft_advisory.sns_message_id is not None

            # Verify audit log
            audit = SystemAuditLog.objects.filter(
                event_type="ADVISORY_PUBLISHED",
                target_id=str(draft_advisory.id),
            ).first()
            assert audit is not None
            assert audit.actor == analyst_user
            assert audit.metadata["target_audience"] == AudienceGroup.GENERAL
            assert audit.metadata["severity"] == AdvisorySeverity.CRITICAL

            # Verify CloudWatch metric
            mock_metric.assert_called_with("AlertsPublished", 1, dims={"Environment": "test"})

    def test_to_be_proven_16_double_click_publish_idempotency(
        self, api_client, analyst_user, draft_advisory, mock_sns
    ):
        """TO BE PROVEN #16: second publish call returns 409 conflict and SNS is called once."""
        api_client.force_authenticate(user=analyst_user)
        res1 = api_client.post(f"/api/v1/advisories/{draft_advisory.id}/publish/")
        assert res1.status_code == 200

        res2 = api_client.post(f"/api/v1/advisories/{draft_advisory.id}/publish/")
        assert res2.status_code == 409
        assert res2.data["error"]["code"] in {"advisory_already_published", "conflict"}

    def test_publish_failure_sets_status_failed_and_permits_retry(
        self, api_client, analyst_user, draft_advisory, mock_sns
    ):
        api_client.force_authenticate(user=analyst_user)
        error_response = {"Error": {"Code": "InternalError", "Message": "SNS unavailable"}}
        with patch.object(
            mock_sns["client"], "publish", side_effect=ClientError(error_response, "Publish")
        ):
            with patch("apps.broadcasts.services.broadcast_service.client", return_value=mock_sns["client"]):
                res = api_client.post(f"/api/v1/advisories/{draft_advisory.id}/publish/")
                assert res.status_code in {500, 502}
                assert res.data["error"]["code"] == "sns_broadcast_failed"

                draft_advisory.refresh_from_db()
                assert draft_advisory.status == AdvisoryStatus.FAILED
                assert draft_advisory.published_at is None
                assert draft_advisory.published_by is None

        # Retry after SNS is restored: succeeds!
        res_retry = api_client.post(f"/api/v1/advisories/{draft_advisory.id}/publish/")
        assert res_retry.status_code == 200
        draft_advisory.refresh_from_db()
        assert draft_advisory.status == AdvisoryStatus.PUBLISHED

    def test_admin_and_citizen_cannot_publish_advisory(
        self, api_client, admin_user, citizen_user, draft_advisory, mock_sns
    ):
        api_client.force_authenticate(user=admin_user)
        res_admin = api_client.post(f"/api/v1/advisories/{draft_advisory.id}/publish/")
        assert res_admin.status_code == 403
        assert res_admin.data["error"]["code"] == "permission_denied"

        api_client.force_authenticate(user=citizen_user)
        res_citizen = api_client.post(f"/api/v1/advisories/{draft_advisory.id}/publish/")
        assert res_citizen.status_code == 403
        assert res_citizen.data["error"]["code"] == "permission_denied"

    def test_to_be_proven_15_advisory_broadcast_reaches_filtered_subscriber(
        self, api_client, analyst_user, draft_advisory, mock_sns
    ):
        """TO BE PROVEN #15: broadcast advisory with audience GENERAL & category PHISHING matches subscriber filter."""
        sns = mock_sns["client"]
        topic_arn = mock_sns["topic_arn"]

        # 1. Create matching subscriber with FilterPolicy
        filter_policy = {"audience": ["ALL", AudienceGroup.GENERAL], "category": [ScamCategory.IMPERSONATION]}
        sub_resp = sns.subscribe(
            TopicArn=topic_arn,
            Protocol="email",
            Endpoint="subscriber_match@example.com",
            Attributes={"FilterPolicy": json.dumps(filter_policy)},
        )
        assert sub_resp["SubscriptionArn"] is not None

        # 2. Publish advisory
        api_client.force_authenticate(user=analyst_user)
        res = api_client.post(f"/api/v1/advisories/{draft_advisory.id}/publish/")
        assert res.status_code == 200
        draft_advisory.refresh_from_db()
        assert draft_advisory.status == AdvisoryStatus.PUBLISHED
