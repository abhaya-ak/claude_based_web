"""
Phase 12 Cloud Resilience and Fault Degradation Test Suite.
Verifies that downstream AWS and cloud service failures (S3, Lambda, SNS, CloudWatch)
fail gracefully without unhandled 500 errors, leaking PII, or leaving orphan resources.
"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from moto import mock_aws
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.broadcasts.models import AdvisorySeverity, ThreatAdvisory
from apps.core import aws
from apps.literacy.models import EducationalGuide, GuideAsset, Tactic
from apps.ops.models import SystemAuditLog
from apps.reports.models import IndicatorType, PaymentMethod, Platform, ScamCategory, ScamReport


def create_valid_test_png() -> bytes:
    bio = io.BytesIO()
    im = Image.new("RGB", (20, 20), color="blue")
    im.save(bio, format="PNG")
    return bio.getvalue()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def educator_user(db):
    user = User.objects.create_user(
        email="educator@resilience.example.com",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )
    return user


@pytest.fixture
def analyst_user(db):
    user = User.objects.create_user(
        email="analyst@resilience.example.com",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )
    return user


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        email="admin@resilience.example.com",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )
    return user


@mock_aws
@pytest.mark.django_db
def test_s3_upload_failure_on_report_submission_returns_503(api_client):
    """
    When S3 raises an error during evidence upload in report creation:
    1. The API must return HTTP 503 storage_unavailable.
    2. Zero ScamReport rows must be committed.
    3. Zero SystemAuditLog rows must be created for the submission.
    4. S3 clean up routine must be invoked to avoid orphan storage keys.
    """
    call_command("seed_playbooks")
    aws.reset_clients()
    s3 = aws.client("s3")
    s3.create_bucket(
        Bucket=settings.EVIDENCE_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
    )

    initial_reports_count = ScamReport.objects.count()
    initial_audit_count = SystemAuditLog.objects.count()

    png_bytes = create_valid_test_png()
    test_file = SimpleUploadedFile("screenshot.png", png_bytes, content_type="image/png")

    data = {
        "client_submission_id": "csub-resilience-s3-fail",
        "category": ScamCategory.PHISHING.value,
        "platform": Platform.WHATSAPP.value,
        "country_code": "MY",
        "currency": "MYR",
        "financial_loss": "0.00",
        "payment_method": PaymentMethod.NONE.value,
        "message_text": "Phishing message for testing S3 fault tolerance.",
        "indicators": json.dumps([{"type": IndicatorType.URL.value, "value": "https://fake-phish-bank.com"}]),
        "evidence": [test_file],
    }

    with patch("apps.reports.services.report_service.evidence.upload_evidence") as mock_upload, \
         patch("apps.reports.services.report_service.evidence.delete_evidence_keys") as mock_cleanup:
        mock_upload.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "Slow Down"}},
            "PutObject",
        )

        response = api_client.post("/api/v1/reports/", data=data, format="multipart")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.data["error"]["code"] == "storage_unavailable"
    assert "temporarily unavailable" in response.data["error"]["message"].lower()

    # DB Integrity assertions
    assert ScamReport.objects.count() == initial_reports_count
    assert SystemAuditLog.objects.count() == initial_audit_count
    assert mock_cleanup.called


@mock_aws
@pytest.mark.django_db
def test_s3_upload_failure_on_guide_asset_returns_503(api_client, educator_user):
    """
    When S3 raises an error during studio guide asset upload:
    1. Returns HTTP 503 storage_unavailable.
    2. Zero GuideAsset rows are created.
    """
    guide = EducationalGuide.objects.create(
        title="S3 Resilience Guide",
        slug="s3-resilience-guide",
        summary="Test resilience to storage faults.",
        body="Guide markdown text.",
        tactics=[Tactic.URGENCY.value],
        audience_groups=["GENERAL"],
        author=educator_user,
    )

    initial_assets_count = GuideAsset.objects.count()

    png_bytes = create_valid_test_png()
    test_file = SimpleUploadedFile("diagram.png", png_bytes, content_type="image/png")

    api_client.force_authenticate(user=educator_user)

    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "InternalError", "Message": "We encountered an internal error. Please try again."}},
        "PutObject",
    )

    with patch("apps.core.aws.client", return_value=mock_s3):
        response = api_client.post(
            f"/api/v1/studio/guides/{guide.id}/assets/",
            data={"file": test_file, "alt_text": "Sample Diagram"},
            format="multipart",
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.data["error"]["code"] == "storage_unavailable"
    assert GuideAsset.objects.count() == initial_assets_count


@mock_aws
@pytest.mark.django_db
def test_lambda_scanner_invocation_failure_fails_open(api_client):
    """
    When AWS Lambda URL scanner fails or times out:
    1. Report submission succeeds with HTTP 201 Created.
    2. Report is saved with scan_status="PENDING".
    3. Failure is logged, but the user is not impacted by 500 error.
    """
    call_command("seed_playbooks")
    aws.reset_clients()
    s3 = aws.client("s3")
    s3.create_bucket(
        Bucket=settings.EVIDENCE_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
    )

    data = {
        "client_submission_id": "csub-resilience-lambda-fail",
        "category": ScamCategory.PHISHING.value,
        "platform": Platform.SMS.value,
        "country_code": "MY",
        "currency": "MYR",
        "financial_loss": "0.00",
        "payment_method": PaymentMethod.NONE.value,
        "message_text": "SMS phish link https://suspicious-loan.com",
        "indicators": json.dumps([{"type": IndicatorType.URL.value, "value": "https://suspicious-loan.com"}]),
    }

    mock_lambda = MagicMock()
    mock_lambda.invoke.side_effect = ClientError(
        {"Error": {"Code": "ServiceException", "Message": "Lambda is overloaded"}},
        "Invoke",
    )

    with patch("apps.core.aws.client", return_value=mock_lambda):
        response = api_client.post("/api/v1/reports/", data=data, format="multipart")

    assert response.status_code == status.HTTP_201_CREATED
    ref = response.data["reference_code"]
    report = ScamReport.objects.get(reference_code=ref)
    assert report.scan_status == "PENDING"


@mock_aws
@pytest.mark.django_db
def test_sns_publish_failure_marks_advisory_failed_and_returns_502(api_client, analyst_user):
    """
    When AWS SNS broadcast raises ClientError during advisory publish:
    1. Returns HTTP 502 sns_broadcast_failed.
    2. ThreatAdvisory status transitions to FAILED.
    3. No unhandled 500 error is thrown.
    """
    advisory = ThreatAdvisory.objects.create(
        title="Urgent Banking Threat Notice",
        body="Do not click unsolicited text links.",
        target_audience="ALL",
        severity=AdvisorySeverity.WARNING.value,
        status="DRAFT",
        created_by=analyst_user,
    )

    api_client.force_authenticate(user=analyst_user)

    mock_sns = MagicMock()
    mock_sns.publish.side_effect = ClientError(
        {"Error": {"Code": "EndpointDisabled", "Message": "Endpoint is disabled"}},
        "Publish",
    )

    with patch("apps.broadcasts.services.broadcast_service.client", return_value=mock_sns):
        response = api_client.post(f"/api/v1/advisories/{advisory.id}/publish/")

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.data["error"]["code"] == "sns_broadcast_failed"

    advisory.refresh_from_db()
    assert advisory.status == "FAILED"


@mock_aws
@pytest.mark.django_db
def test_cloudwatch_metrics_failure_returns_degraded_structure_without_crashing(api_client, admin_user):
    """
    When AWS CloudWatch fails or times out during telemetry retrieval:
    1. Telemetry endpoint returns HTTP 200 OK.
    2. Response includes degraded=True and safe fallback zeroed arrays.
    3. Admin user experience is maintained without 500 crashes.
    """
    api_client.force_authenticate(user=admin_user)

    mock_cw = MagicMock()
    mock_cw.get_metric_data.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "CloudWatch get_metric_data access denied"}},
        "GetMetricData",
    )

    with patch("apps.ops.services.cloudwatch_service.client", return_value=mock_cw):
        response = api_client.get("/api/v1/admin-portal/telemetry/metrics/?range=24h")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["degraded"] is True
    assert "infrastructure" in response.data
    assert "operations" in response.data
