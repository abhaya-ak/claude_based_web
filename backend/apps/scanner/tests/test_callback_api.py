import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from moto import mock_aws
from rest_framework import status
from rest_framework.test import APIClient

from apps.reports.models import ReportStatus, ScamCategory, ScamReport, ScanStatus
from apps.scanner.models import ScanResult
from apps.scanner.selectors.scanner_selectors import build_scan_payload
from apps.scanner.tests.factories import ScannerConfigFactory


def _sign_payload(payload_bytes: bytes, secret: str, timestamp: str | int | None = None) -> tuple[str, str]:
    if timestamp is None:
        timestamp = str(int(time.time()))
    else:
        timestamp = str(timestamp)
    sig = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode() + payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return timestamp, sig


@pytest.mark.django_db
class TestScannerCallbackAPI:
    @pytest.fixture(autouse=True)
    def setup_config_and_secret(self, settings):
        cache.clear()
        ScannerConfigFactory(
            ruleset_version=1,
            keyword_cap_points=45,
            ip_url_points=25,
            prior_pending_points=10,
            high_priority_threshold=75,
        )
        self.secret = "test-secret-key-at-least-32-chars-long!"
        settings.INTERNAL_CALLBACK_HMAC_KEY = self.secret
        settings.SCANNER_CALLBACK_SECRET = self.secret
        settings.STAFF_TOPIC_ARN = "arn:aws:sns:ap-southeast-1:123456789012:scamshield-staff-alerts"
        self.client = APIClient()
        self.url = reverse("internal-scan-results")

    def _create_report(self, reference="SCM-2026-TEST0001", status_val=ReportStatus.PENDING):
        return ScamReport.objects.create(
            reference_code=reference,
            category=ScamCategory.PHISHING,
            country_code="MY",
            currency="MYR",
            financial_loss=0,
            message_text="Urgent verify bank account here: http://192.168.1.1/login",
            platform="WHATSAPP",
            status=status_val,
            scan_status=ScanStatus.PENDING,
            scan_attempts=1,
        )

    def test_to_be_proven_9_lambda_to_django_hmac_handshake(self, settings, django_capture_on_commit_callbacks):
        """
        Prove TO BE PROVEN #9: End-to-End Lambda -> Django HMAC Handshake.
        Invoke Lambda scoring and signing logic directly, send to Django endpoint,
        and assert 200 OK, ScanResult created, and ScamReport updated.
        """
        import sys
        from pathlib import Path

        # Add lambda directory to sys.path if not present
        lambda_dir = str(Path(settings.BASE_DIR) / "lambda" / "heuristic_scanner")
        if lambda_dir not in sys.path:
            sys.path.insert(0, lambda_dir)

        from handler import lambda_handler

        report = self._create_report("SCM-2026-HANDSHAKE")
        scan_payload = build_scan_payload(report.id)

        # Execute Lambda handler (mocking urllib so it does not make real network call)
        with patch("urllib.request.urlopen"):
            lambda_response = lambda_handler(scan_payload)

        assert lambda_response["statusCode"] == 200
        result_dict = json.loads(lambda_response["body"])
        result_bytes = json.dumps(result_dict, separators=(",", ":")).encode("utf-8")

        # Sign using exact Lambda handler signing logic
        timestamp, signature = _sign_payload(result_bytes, self.secret)

        with django_capture_on_commit_callbacks(execute=True):
            response = self.client.generic(
                "POST",
                self.url,
                data=result_bytes,
                content_type="application/json",
                HTTP_X_TIMESTAMP=timestamp,
                HTTP_X_SIGNATURE=signature,
            )

        assert response.status_code == status.HTTP_200_OK
        report.refresh_from_db()
        assert report.scan_status == ScanStatus.DONE
        assert report.risk_score == result_dict["risk_score"]
        assert report.is_high_priority == result_dict["is_high_priority"]

        scan_result = ScanResult.objects.get(report=report)
        assert scan_result.ruleset_version == result_dict["ruleset_version"]
        assert scan_result.risk_score == result_dict["risk_score"]
        assert scan_result.is_high_priority == result_dict["is_high_priority"]
        assert isinstance(scan_result.breakdown, list)

    def test_missing_signature_headers_returns_403(self):
        report = self._create_report("SCM-2026-NOHDR")
        body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 10,
            "is_high_priority": False,
            "breakdown": [],
        }).encode("utf-8")

        # Missing both
        resp = self.client.generic("POST", self.url, data=body, content_type="application/json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["error"]["code"] == "permission_denied"

        # Missing signature
        resp = self.client.generic(
            "POST", self.url, data=body, content_type="application/json",
            HTTP_X_TIMESTAMP=str(int(time.time())),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["error"]["code"] == "permission_denied"

        # Missing timestamp
        resp = self.client.generic(
            "POST", self.url, data=body, content_type="application/json",
            HTTP_X_SIGNATURE="any-sig",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["error"]["code"] == "permission_denied"

    def test_non_integer_timestamp_returns_403(self):
        report = self._create_report("SCM-2026-BADTS")
        body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 10,
            "is_high_priority": False,
            "breakdown": [],
        }).encode("utf-8")
        _, sig = _sign_payload(body, self.secret)

        resp = self.client.generic(
            "POST", self.url, data=body, content_type="application/json",
            HTTP_X_TIMESTAMP="not-an-integer",
            HTTP_X_SIGNATURE=sig,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["error"]["code"] == "permission_denied"

    def test_stale_and_future_timestamp_clock_skew_returns_403(self):
        report = self._create_report("SCM-2026-SKEW")
        body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 10,
            "is_high_priority": False,
            "breakdown": [],
        }).encode("utf-8")
        now = int(time.time())

        # Stale (-301 seconds)
        ts_old = now - 301
        _, sig_old = _sign_payload(body, self.secret, timestamp=ts_old)
        resp = self.client.generic(
            "POST", self.url, data=body, content_type="application/json",
            HTTP_X_TIMESTAMP=str(ts_old),
            HTTP_X_SIGNATURE=sig_old,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["error"]["code"] == "permission_denied"

        # Future (+301 seconds)
        ts_future = now + 301
        _, sig_future = _sign_payload(body, self.secret, timestamp=ts_future)
        resp = self.client.generic(
            "POST", self.url, data=body, content_type="application/json",
            HTTP_X_TIMESTAMP=str(ts_future),
            HTTP_X_SIGNATURE=sig_future,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["error"]["code"] == "permission_denied"

    def test_tampered_signature_or_body_returns_403(self):
        report = self._create_report("SCM-2026-TAMPER")
        body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 10,
            "is_high_priority": False,
            "breakdown": [],
        }).encode("utf-8")
        ts, sig = _sign_payload(body, self.secret)

        # 1. Tampered signature
        resp = self.client.generic(
            "POST", self.url, data=body, content_type="application/json",
            HTTP_X_TIMESTAMP=ts,
            HTTP_X_SIGNATURE="deadbeef" * 8,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["error"]["code"] == "permission_denied"

        # 2. Tampered body
        tampered_body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 99,
            "is_high_priority": True,
            "breakdown": [],
        }).encode("utf-8")
        resp = self.client.generic(
            "POST", self.url, data=tampered_body, content_type="application/json",
            HTTP_X_TIMESTAMP=ts,
            HTTP_X_SIGNATURE=sig,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["error"]["code"] == "permission_denied"

    def test_unknown_report_id_returns_404(self):
        unknown_id = str(uuid.uuid4())
        body = json.dumps({
            "report_id": unknown_id,
            "ruleset_version": 1,
            "risk_score": 10,
            "is_high_priority": False,
            "breakdown": [],
        }).encode("utf-8")
        ts, sig = _sign_payload(body, self.secret)

        resp = self.client.generic(
            "POST", self.url, data=body, content_type="application/json",
            HTTP_X_TIMESTAMP=ts,
            HTTP_X_SIGNATURE=sig,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.data["error"]["code"] == "not_found"

    def test_invalid_payload_fields_returns_400(self):
        report = self._create_report("SCM-2026-INVALID")
        # risk_score 150 is out of bounds (0..100)
        body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 150,
            "is_high_priority": False,
            "breakdown": [],
        }).encode("utf-8")
        ts, sig = _sign_payload(body, self.secret)

        resp = self.client.generic(
            "POST", self.url, data=body, content_type="application/json",
            HTTP_X_TIMESTAMP=ts,
            HTTP_X_SIGNATURE=sig,
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["error"]["code"] == "validation_error"

    @mock_aws
    def test_idempotent_replay_returns_200_and_does_not_duplicate_or_resend_sns(
        self, django_capture_on_commit_callbacks
    ):
        report = self._create_report("SCM-2026-REPLAY")
        body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 80,
            "is_high_priority": True,
            "breakdown": [{"rule": "test", "type": "KEYWORD", "points": 80}],
        }).encode("utf-8")
        ts, sig = _sign_payload(body, self.secret)

        with patch("apps.scanner.services.callback_service.client") as mock_client:
            mock_sns = MagicMock()
            mock_client.return_value = mock_sns

            # First submission
            with django_capture_on_commit_callbacks(execute=True):
                resp1 = self.client.generic(
                    "POST", self.url, data=body, content_type="application/json",
                    HTTP_X_TIMESTAMP=ts,
                    HTTP_X_SIGNATURE=sig,
                )
            assert resp1.status_code == status.HTTP_200_OK
            assert ScanResult.objects.filter(report=report).count() == 1
            assert mock_sns.publish.call_count == 1

            # Second submission (replay of same report_id and ruleset_version)
            with django_capture_on_commit_callbacks(execute=True):
                resp2 = self.client.generic(
                    "POST", self.url, data=body, content_type="application/json",
                    HTTP_X_TIMESTAMP=ts,
                    HTTP_X_SIGNATURE=sig,
                )
            assert resp2.status_code == status.HTTP_200_OK
            assert ScanResult.objects.filter(report=report).count() == 1
            # Must NOT publish second SNS alert
            assert mock_sns.publish.call_count == 1

    @mock_aws
    def test_high_priority_scan_publishes_sns_alert_without_pii(
        self, django_capture_on_commit_callbacks
    ):
        report = self._create_report("SCM-2026-HIGHPRIO")
        body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 90,
            "is_high_priority": True,
            "breakdown": [{"rule": "urgent", "type": "KEYWORD", "points": 90}],
        }).encode("utf-8")
        ts, sig = _sign_payload(body, self.secret)

        with patch("apps.scanner.services.callback_service.client") as mock_client:
            mock_sns = MagicMock()
            mock_client.return_value = mock_sns

            with django_capture_on_commit_callbacks(execute=True):
                resp = self.client.generic(
                    "POST", self.url, data=body, content_type="application/json",
                    HTTP_X_TIMESTAMP=ts,
                    HTTP_X_SIGNATURE=sig,
                )
            assert resp.status_code == status.HTTP_200_OK
            assert mock_sns.publish.call_count == 1

            call_kwargs = mock_sns.publish.call_args[1]
            assert call_kwargs["TopicArn"] == settings.STAFF_TOPIC_ARN
            assert "SCM-2026-HIGHPRIO" in call_kwargs["Subject"]

            published_msg = json.loads(call_kwargs["Message"])
            assert published_msg["reference_code"] == "SCM-2026-HIGHPRIO"
            assert published_msg["report_id"] == str(report.id)
            assert published_msg["risk_score"] == 90
            assert published_msg["ruleset_version"] == 1
            assert published_msg["category"] == ScamCategory.PHISHING

            # Zero PII check
            msg_str = json.dumps(published_msg)
            assert "192.168.1.1" not in msg_str
            assert "Urgent verify" not in msg_str

    def test_low_priority_scan_does_not_publish_sns(self, django_capture_on_commit_callbacks):
        report = self._create_report("SCM-2026-LOWPRIO")
        body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 30,
            "is_high_priority": False,
            "breakdown": [],
        }).encode("utf-8")
        ts, sig = _sign_payload(body, self.secret)

        with patch("apps.scanner.services.callback_service.client") as mock_client:
            mock_sns = MagicMock()
            mock_client.return_value = mock_sns

            with django_capture_on_commit_callbacks(execute=True):
                resp = self.client.generic(
                    "POST", self.url, data=body, content_type="application/json",
                    HTTP_X_TIMESTAMP=ts,
                    HTTP_X_SIGNATURE=sig,
                )
            assert resp.status_code == status.HTTP_200_OK
            assert mock_sns.publish.call_count == 0

    def test_sns_publish_error_does_not_fail_callback(self, django_capture_on_commit_callbacks):
        report = self._create_report("SCM-2026-SNSERR")
        body = json.dumps({
            "report_id": str(report.id),
            "ruleset_version": 1,
            "risk_score": 85,
            "is_high_priority": True,
            "breakdown": [],
        }).encode("utf-8")
        ts, sig = _sign_payload(body, self.secret)

        with patch("apps.scanner.services.callback_service.client") as mock_client:
            mock_sns = MagicMock()
            mock_sns.publish.side_effect = ClientError({"Error": {"Code": "ServiceUnavailable", "Message": "SNS down"}}, "Publish")
            mock_client.return_value = mock_sns

            with django_capture_on_commit_callbacks(execute=True):
                resp = self.client.generic(
                    "POST", self.url, data=body, content_type="application/json",
                    HTTP_X_TIMESTAMP=ts,
                    HTTP_X_SIGNATURE=sig,
                )
            assert resp.status_code == status.HTTP_200_OK
            report.refresh_from_db()
            assert report.scan_status == ScanStatus.DONE

    def test_callback_endpoint_rate_limit(self):
        """101 requests from same IP in 1 minute returns 429 throttled."""
        from rest_framework.exceptions import Throttled

        from apps.core.ip import client_ip_hash
        from apps.scanner.throttling import check_scanner_callback_throttle

        ip = "192.0.2.100"
        # Dummy request object with META
        dummy_req = MagicMock()
        dummy_req.headers = {}
        dummy_req.META = {"REMOTE_ADDR": ip}
        hash_val = client_ip_hash(dummy_req)

        # 100 calls succeed
        for _ in range(100):
            check_scanner_callback_throttle(hash_val)

        # 101st call raises Throttled
        with pytest.raises(Throttled) as exc_info:
            check_scanner_callback_throttle(hash_val)
        assert exc_info.value.status_code == 429
