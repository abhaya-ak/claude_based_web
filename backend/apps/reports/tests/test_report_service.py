import hashlib
import io
import logging
import re
import threading
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.conf import settings
from moto import mock_aws
from PIL import Image

from apps.accounts.models import Role, User
from apps.core import aws
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.reports.constants import CROCKFORD_ALPHABET
from apps.reports.models import (
    IndicatorType,
    PaymentMethod,
    Platform,
    ReportEvidence,
    ReportIndicator,
    ScamCategory,
    ScamReport,
)
from apps.reports.normalizers import normalize_bank_account
from apps.reports.services.report_service import (
    create_report,
    generate_reference_code,
    track_report,
)


def create_test_png() -> bytes:
    bio = io.BytesIO()
    im = Image.new("RGB", (20, 20), color="green")
    im.save(bio, format="PNG")
    return bio.getvalue()


@pytest.mark.django_db
class TestReferenceCodeGeneration:
    def test_crockford_reference_format_and_alphabet(self):
        code = generate_reference_code()
        # Pattern: SCM-<YYYY>-<8 Crockford chars>
        assert re.match(r"^SCM-\d{4}-[0-9A-HJKMNP-Z]{8}$", code)
        chars = code.split("-")[2]
        assert len(chars) == 8
        for c in chars:
            assert c in CROCKFORD_ALPHABET
            # Explicit ban on confusing letters per Crockford spec
            assert c not in ("I", "L", "O", "U")

    def test_collision_retry_mechanism(self):
        call_count = 0

        def mock_exists_side_effect():
            nonlocal call_count
            call_count += 1
            # Collide twice, then succeed
            return call_count <= 2

        with patch.object(ScamReport.objects, "filter") as mock_filter:
            mock_filter.return_value.exists.side_effect = mock_exists_side_effect
            code = generate_reference_code()
            assert code.startswith("SCM-")
            assert call_count == 3


@pytest.mark.django_db
class TestIndicatorHMACDeterministicAndKeyDependent:
    def test_bank_account_hmac_deterministic_and_key_dependent(self, monkeypatch):
        # D75: Bank-account HMAC must be deterministic and key-dependent
        acc_num = " 1234-5678-9012 "
        norm1, _ = normalize_bank_account(acc_num)
        norm2, _ = normalize_bank_account(acc_num)
        assert norm1 == norm2  # Deterministic

        # Change HMAC key
        monkeypatch.setattr(settings, "INDICATOR_HMAC_KEY", "different-secret-key-32-chars-long!")
        norm_diff, _ = normalize_bank_account(acc_num)
        assert norm1 != norm_diff  # Key-dependent


@mock_aws
@pytest.mark.django_db
class TestReportServiceCreation:
    def setup_method(self, method=None):
        aws.reset_clients()
        s3 = aws.client("s3")
        s3.create_bucket(
            Bucket=settings.EVIDENCE_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )

    def test_anonymous_report_creation_and_audit(self):
        result = create_report(
            category=ScamCategory.PHISHING,
            platform=Platform.WHATSAPP,
            message_text="Urgent: Your account is suspended, click https://fakebank.com/login",
            country_code="MY",
            currency="MYR",
            financial_loss=Decimal("0.00"),
            payment_method=PaymentMethod.NONE,
            admin_area="Selangor",
            indicators=[
                {"type": IndicatorType.URL, "value": "https://fakebank.com/login"},
                {"type": IndicatorType.PHONE, "value": "0123456789"},
            ],
            anonymous=True,
            ip_hash="test_anon_ip_hash",
        )

        assert result.is_replay is False
        assert result.access_key is not None
        assert len(result.access_key) == 32  # 128-bit hex string

        report = result.report
        assert report.is_anonymous is True
        assert report.reporter is None
        assert report.country_code == "MY"
        assert report.admin_area == "Selangor"

        # Verify access key hash
        expected_hash = hashlib.sha256(result.access_key.encode("utf-8")).hexdigest()
        assert report.access_key_hash == expected_hash

        # Verify indicators: 2 submitted + 1 auto-derived DOMAIN from URL
        indicators = ReportIndicator.objects.filter(report=report)
        assert indicators.count() == 3
        types = set(indicators.values_list("type", flat=True))
        assert types == {IndicatorType.URL, IndicatorType.PHONE, IndicatorType.DOMAIN}

        # Verify derived DOMAIN indicator
        domain_ind = indicators.filter(type=IndicatorType.DOMAIN).first()
        assert domain_ind.normalized_value == "fakebank.com"

        # Verify audit log has no PII and actor is None
        audit_log = SystemAuditLog.objects.filter(
            event_type=AuditEventType.REPORT_SUBMITTED,
            target_id=str(report.id),
        ).first()
        assert audit_log is not None
        assert audit_log.actor is None
        assert audit_log.actor_ip_hash == "test_anon_ip_hash"
        assert audit_log.metadata["category"] == "PHISHING"
        assert audit_log.metadata["indicator_count"] == 3
        assert audit_log.metadata["file_count"] == 0

    def test_authenticated_report_creation(self):
        user = User.objects.create_user(
            email="reporter@example.com",
            password="StrongPassword123!",
            role=Role.CITIZEN,
        )

        result = create_report(
            category=ScamCategory.ECOMMERCE_FRAUD,
            platform=Platform.WEBSITE,
            message_text="Paid for item on fake marketplace, never delivered.",
            country_code="MY",
            currency="MYR",
            financial_loss=Decimal("150.00"),
            payment_method=PaymentMethod.BANK_TRANSFER,
            indicators=[
                {"type": IndicatorType.BANK_ACCOUNT, "value": "1234567890"},
            ],
            anonymous=False,
            user=user,
            ip_hash="test_auth_ip_hash",
        )

        assert result.is_replay is False
        assert result.access_key is None

        report = result.report
        assert report.is_anonymous is False
        assert report.reporter == user
        assert report.access_key_hash is None
        assert report.financial_loss == Decimal("150.00")

        # Verify audit log links to user
        audit_log = SystemAuditLog.objects.filter(
            event_type=AuditEventType.REPORT_SUBMITTED,
            target_id=str(report.id),
        ).first()
        assert audit_log is not None
        assert audit_log.actor == user
        assert audit_log.actor_ip_hash == "test_auth_ip_hash"

    def test_valid_token_with_anonymous_true_leaves_no_link_to_user(self):
        # D69: valid auth token + anonymous=true leaves no link to user anywhere
        user = User.objects.create_user(
            email="secret_reporter@example.com",
            password="StrongPassword123!",
            role=Role.CITIZEN,
        )

        result = create_report(
            category=ScamCategory.IMPERSONATION,
            platform=Platform.TELEGRAM,
            message_text="Impersonating tax officer asking for money.",
            country_code="NP",
            currency="NPR",
            financial_loss=Decimal("5000.00"),
            payment_method=PaymentMethod.E_WALLET,
            indicators=[{"type": IndicatorType.PHONE, "value": "+9779841234567"}],
            anonymous=True,
            user=user,
            ip_hash="secret_ip_hash",
        )

        report = result.report
        assert report.is_anonymous is True
        assert report.reporter is None
        assert result.access_key is not None

        # Verify audit log has no link to user
        audit_log = SystemAuditLog.objects.filter(
            event_type=AuditEventType.REPORT_SUBMITTED,
            target_id=str(report.id),
        ).first()
        assert audit_log is not None
        assert audit_log.actor is None
        assert str(user.id) not in str(audit_log.metadata)
        assert user.email not in str(audit_log.metadata)

    def test_report_creation_leaves_no_pii_in_logs_or_audit(self, caplog: pytest.LogCaptureFixture):
        # Standing Rule: a real request leaves no message text, indicator, filename or IP in any log record or audit metadata
        raw_ip = "198.51.100.42"
        salt_hash = "hmac_sha256_hash_42"
        secret_msg = "SUPER_SECRET_SCAM_MESSAGE_TEXT_99999"
        raw_phone = "+60123456789"
        png_bytes = create_test_png()

        with caplog.at_level(logging.DEBUG):
            result = create_report(
                category=ScamCategory.PHISHING,
                platform=Platform.SMS,
                message_text=secret_msg,
                country_code="MY",
                currency="MYR",
                indicators=[{"type": IndicatorType.PHONE, "value": raw_phone}],
                evidence_files=[png_bytes],
                anonymous=True,
                ip_hash=salt_hash,
            )

        report = result.report
        # 1. Audit metadata assertions
        audit_log = SystemAuditLog.objects.filter(target_id=str(report.id)).first()
        assert audit_log is not None
        audit_str = str(audit_log.metadata)
        assert secret_msg not in audit_str
        assert raw_phone not in audit_str
        assert raw_ip not in audit_str
        assert "evidence/" not in audit_str
        assert ".png" not in audit_str

        # 2. Log records assertions
        all_logs = " ".join(r.getMessage() for r in caplog.records)
        assert secret_msg not in all_logs
        assert raw_phone not in all_logs
        assert raw_ip not in all_logs

    def test_idempotency_replay_creates_zero_new_rows_and_no_new_s3_objects(self):
        # D62: replay returns 200 with same reference, creates 0 rows, 0 S3 objects
        sub_id = uuid.uuid4()
        png_bytes = create_test_png()

        # First submission
        res1 = create_report(
            category=ScamCategory.PHISHING,
            platform=Platform.EMAIL,
            message_text="Phishing email test narrative",
            country_code="MY",
            currency="MYR",
            indicators=[{"type": IndicatorType.EMAIL, "value": "scammer@bad.test"}],
            evidence_files=[png_bytes],
            client_submission_id=sub_id,
            anonymous=True,
        )
        assert res1.is_replay is False
        assert res1.access_key is not None
        initial_report_count = ScamReport.objects.count()
        initial_indicator_count = ReportIndicator.objects.count()
        initial_evidence_count = ReportEvidence.objects.count()

        # Second submission (replay)
        res2 = create_report(
            category=ScamCategory.PHISHING,
            platform=Platform.EMAIL,
            message_text="Phishing email test narrative",
            country_code="MY",
            currency="MYR",
            indicators=[{"type": IndicatorType.EMAIL, "value": "scammer@bad.test"}],
            evidence_files=[png_bytes],
            client_submission_id=sub_id,
            anonymous=True,
        )
        assert res2.is_replay is True
        assert res2.access_key is None  # Access key never issued twice
        assert res2.report.id == res1.report.id
        assert res2.report.reference_code == res1.report.reference_code

        # Assert no new DB rows created
        assert ScamReport.objects.count() == initial_report_count
        assert ReportIndicator.objects.count() == initial_indicator_count
        assert ReportEvidence.objects.count() == initial_evidence_count

    def test_s3_upload_rollback_on_db_failure(self):
        # D59: if DB write fails, delete uploaded S3 keys
        png_bytes = create_test_png()
        s3 = aws.client("s3")

        with patch("apps.reports.models.ScamReport.objects.create") as mock_create:
            mock_create.side_effect = RuntimeError("Simulated DB fatal crash")

            with pytest.raises(RuntimeError):
                create_report(
                    category=ScamCategory.PHISHING,
                    platform=Platform.SMS,
                    message_text="Test message for S3 rollback",
                    country_code="MY",
                    currency="MYR",
                    indicators=[{"type": IndicatorType.PHONE, "value": "0123456789"}],
                    evidence_files=[png_bytes],
                    anonymous=True,
                )

        # Verify S3 has 0 objects remaining in bucket
        res = s3.list_objects_v2(Bucket=settings.EVIDENCE_BUCKET)
        assert res.get("KeyCount", 0) == 0

    def test_scanner_stub_failure_does_not_abort_submission(self):
        with patch("apps.scanner.services.scanner_service.dispatch_scan") as mock_scan:
            mock_scan.side_effect = Exception("Scanner lambda error")

            # Must succeed despite scanner stub failure
            res = create_report(
                category=ScamCategory.PHISHING,
                platform=Platform.SMS,
                message_text="Scanner test message",
                country_code="MY",
                currency="MYR",
                indicators=[{"type": IndicatorType.PHONE, "value": "0123456789"}],
                anonymous=True,
            )
            assert res.report is not None


@mock_aws
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
class TestConcurrentSameKeyRace:
    def setup_method(self, method=None):
        aws.reset_clients()
        s3 = aws.client("s3")
        s3.create_bucket(
            Bucket=settings.EVIDENCE_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )

    def test_concurrent_same_key_race_returns_replay_without_500(self):
        # D70: Two concurrent requests with the same Idempotency-Key
        sub_id = uuid.uuid4()
        png_bytes = create_test_png()
        results = []
        errors = []

        def worker():
            try:
                res = create_report(
                    category=ScamCategory.PHISHING,
                    platform=Platform.WHATSAPP,
                    message_text="Concurrent submission message test",
                    country_code="MY",
                    currency="MYR",
                    indicators=[{"type": IndicatorType.PHONE, "value": "0123456789"}],
                    evidence_files=[png_bytes],
                    client_submission_id=sub_id,
                    anonymous=True,
                )
                results.append(res)
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Neither thread must crash or error
        assert len(errors) == 0
        assert len(results) == 2
        # Both must return the identical report reference
        assert results[0].report.reference_code == results[1].report.reference_code
        # Exactly one must be replay and one initial
        replays = [r.is_replay for r in results]
        assert True in replays
        assert False in replays
        # DB must have exactly 1 report
        assert ScamReport.objects.filter(client_submission_id=sub_id).count() == 1


@pytest.mark.django_db
class TestTrackReportService:
    def test_track_anonymous_report_with_valid_key(self):
        result = create_report(
            category=ScamCategory.PHISHING,
            platform=Platform.SMS,
            message_text="Track report test message",
            country_code="MY",
            currency="MYR",
            indicators=[{"type": IndicatorType.PHONE, "value": "0123456789"}],
            anonymous=True,
        )

        report, playbook = track_report(
            reference_code=result.report.reference_code,
            access_key=result.access_key,
        )
        assert report.id == result.report.id
        assert "title" in playbook
        assert len(playbook["steps"]) > 0

    def test_track_authenticated_report_by_owner(self):
        user = User.objects.create_user(
            email="owner_track@example.com",
            password="StrongPassword123!",
            role=Role.CITIZEN,
        )
        result = create_report(
            category=ScamCategory.FAKE_JOB,
            platform=Platform.TELEGRAM,
            message_text="Job scam test message",
            country_code="MY",
            currency="MYR",
            indicators=[{"type": IndicatorType.PHONE, "value": "0123456789"}],
            anonymous=False,
            user=user,
        )

        report, playbook = track_report(
            reference_code=result.report.reference_code,
            user=user,
        )
        assert report.id == result.report.id
        assert playbook is not None
