import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.management import call_command
from moto import mock_aws
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core import aws
from apps.reports.models import (
    IndicatorType,
    Platform,
    ReportStatus,
    ScamCategory,
    ScamReport,
)
from apps.scanner.models import HeuristicRule, RuleType, ScannerConfig
from apps.scanner.selectors.scanner_selectors import build_scan_payload
from apps.scanner.services.scanner_service import dispatch_scan


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_dispatch@example.com",
        password="AdminPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def sample_report(db):
    report = ScamReport.objects.create(
        reference_code=f"SCM-2026-{uuid.uuid4().hex[:8]}",
        category=ScamCategory.PHISHING,
        platform=Platform.SMS,
        message_text="Urgent! Your bank account is locked. Verify at http://scam.xyz/login",
        country_code="MY",
        currency="MYR",
        status=ReportStatus.PENDING,
    )
    report.indicators.create(
        type=IndicatorType.URL,
        raw_value="http://scam.xyz/login",
        normalized_value="scam.xyz/login",
        display_value="scam.xyz/login",
    )
    report.indicators.create(
        type=IndicatorType.PHONE,
        raw_value="+60123456789",
        normalized_value="+60123456789",
        display_value="+60123456789",
    )
    return report


@pytest.mark.django_db
class TestScanPayloadAssembly:
    def test_build_scan_payload_structure(self, sample_report, admin_user):
        ScannerConfig.objects.get_or_create(id=1, defaults={"ruleset_version": 3})
        HeuristicRule.objects.create(
            rule_type=RuleType.KEYWORD,
            pattern="urgent",
            weight=15,
            is_active=True,
            created_by=admin_user,
        )
        HeuristicRule.objects.create(
            rule_type=RuleType.TLD,
            pattern=".xyz",
            weight=25,
            is_active=True,
            created_by=admin_user,
        )

        payload = build_scan_payload(sample_report.id)

        assert payload["report_id"] == str(sample_report.id)
        assert payload["message_text"] == sample_report.message_text
        assert payload["ruleset_version"] >= 1
        assert "config" in payload
        assert payload["config"]["keyword_cap_points"] == 45

        # Rules grouped
        assert len(payload["rules"]["KEYWORD"]) == 1
        assert payload["rules"]["KEYWORD"][0]["pattern"] == "urgent"
        assert len(payload["rules"]["TLD"]) == 1
        assert payload["rules"]["TLD"][0]["pattern"] == ".xyz"

        # Indicators and extracted hosts
        assert len(payload["indicators"]) == 2
        url_ind = next(i for i in payload["indicators"] if i["type"] == "URL")
        assert url_ind["host"] == "scam.xyz"
        phone_ind = next(i for i in payload["indicators"] if i["type"] == "PHONE")
        assert phone_ind["host"] == ""

    def test_prior_pending_counts_aggregated_accurately(self, sample_report):
        # Another PENDING report with the same phone
        other_pending = ScamReport.objects.create(
            reference_code=f"SCM-2026-{uuid.uuid4().hex[:8]}",
            category=ScamCategory.OTHER,
            platform=Platform.WHATSAPP,
            message_text="Other scam",
            status=ReportStatus.PENDING,
            country_code="MY",
            currency="MYR",
        )
        other_pending.indicators.create(
            type=IndicatorType.PHONE,
            raw_value="+60123456789",
            normalized_value="+60123456789",
            display_value="+60123456789",
        )

        # A non-pending (e.g. VERIFIED) report with the same phone should NOT be counted
        resolved_report = ScamReport.objects.create(
            reference_code=f"SCM-2026-{uuid.uuid4().hex[:8]}",
            category=ScamCategory.FAKE_JOB,
            platform=Platform.TELEGRAM,
            message_text="Job scam",
            status=ReportStatus.VERIFIED,
            country_code="MY",
            currency="MYR",
        )
        resolved_report.indicators.create(
            type=IndicatorType.PHONE,
            raw_value="+60123456789",
            normalized_value="+60123456789",
            display_value="+60123456789",
        )

        payload = build_scan_payload(sample_report.id)
        assert payload["prior_pending_counts"] == {"+60123456789": 1}

    def test_payload_assembly_lean_queries(self, sample_report, django_assert_num_queries):
        ScannerConfig.objects.get_or_create(id=1, defaults={"ruleset_version": 1})
        # Payload assembly executes exactly 4 lean queries (report with indicators join, rules, config, prior counts)
        with django_assert_num_queries(4):
            build_scan_payload(sample_report.id)


@pytest.mark.django_db
class TestDispatchScanService:
    def test_dispatch_scan_invokes_lambda_and_updates_report(self, sample_report):
        mock_lambda = MagicMock()
        with patch.object(aws, "client", return_value=mock_lambda):
            dispatch_scan(sample_report.id)

            assert mock_lambda.invoke.called
            call_kwargs = mock_lambda.invoke.call_args[1]
            assert call_kwargs["InvocationType"] == "Event"
            assert "scamshield-heuristic-scanner" in call_kwargs["FunctionName"]

            payload = json.loads(call_kwargs["Payload"])
            assert payload["report_id"] == str(sample_report.id)

        sample_report.refresh_from_db()
        assert sample_report.scan_attempts == 1
        assert sample_report.scan_dispatched_at is not None

    def test_dispatch_scan_failure_tolerance(self, sample_report):
        """TO BE PROVEN #10: Failure in boto3 invoke never raises or crashes report flow."""
        mock_lambda = MagicMock()
        mock_lambda.invoke.side_effect = RuntimeError("Simulated AWS Lambda connection timeout")

        with patch.object(aws, "client", return_value=mock_lambda):
            # Must not raise exception
            dispatch_scan(sample_report.id)

        sample_report.refresh_from_db()
        assert sample_report.scan_status == "PENDING"
        assert sample_report.scan_attempts == 1

    @mock_aws
    def test_create_report_api_with_failing_scanner_returns_201(self, api_client):
        """End-to-end proof of TO BE PROVEN #10 through POST /api/v1/reports/."""
        aws.reset_clients()
        s3 = aws.client("s3")
        s3.create_bucket(
            Bucket=settings.EVIDENCE_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        call_command("seed_playbooks")

        mock_lambda = MagicMock()
        mock_lambda.invoke.side_effect = Exception("AWS Lambda service unavailable")

        with patch.object(aws, "client", return_value=mock_lambda):
            res = api_client.post(
                "/api/v1/reports/",
                data={
                    "category": ScamCategory.PHISHING,
                    "platform": Platform.SMS,
                    "message_text": "Phishing message for failure tolerance test",
                    "country_code": "MY",
                    "currency": "MYR",
                    "indicators": json.dumps([{"type": "PHONE", "value": "+60123456789"}]),
                },
                format="multipart",
            )
            assert res.status_code == 201
            data = res.json()
            ref_code = data["reference_code"]

            report = ScamReport.objects.get(reference_code=ref_code)
            assert report.scan_status == "PENDING"
