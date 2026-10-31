import uuid
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.tests.factories import UserFactory
from apps.reports.models import (
    IndicatorType,
    PaymentMethod,
    Platform,
    RecoveryPlaybook,
    ReportEvidence,
    ReportIndicator,
    ReportStatus,
    ScamCategory,
    ScamReport,
    ScanStatus,
)
from apps.reports.tests.factories import (
    RecoveryPlaybookFactory,
    ReportEvidenceFactory,
    ReportIndicatorFactory,
    ScamReportFactory,
)


@pytest.mark.django_db
class TestScamReportConstraints:
    def test_duplicate_reference_code_fails(self):
        """Failing-insert test for unique reference_code."""
        ScamReportFactory(reference_code="SCM-2026-UNIQUE01")

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReportFactory(reference_code="SCM-2026-UNIQUE01")
        assert "reference_code" in str(excinfo.value)

        # Positive control: distinct reference code succeeds
        distinct = ScamReportFactory(reference_code="SCM-2026-UNIQUE02")
        assert distinct.reference_code == "SCM-2026-UNIQUE02"

    def test_duplicate_client_submission_id_fails(self):
        """Failing-insert test for unique client_submission_id."""
        sub_id = uuid.uuid4()
        ScamReportFactory(client_submission_id=sub_id)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReportFactory(client_submission_id=sub_id)
        assert "client_submission_id" in str(excinfo.value)

        # Positive control: distinct client_submission_id succeeds
        distinct_sub = uuid.uuid4()
        distinct = ScamReportFactory(client_submission_id=distinct_sub)
        assert distinct.client_submission_id == distinct_sub

    def test_anonymous_with_reporter_fails(self):
        """Failing-insert test for ck_report_anon_reporter."""
        reporter = UserFactory()

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReportFactory(is_anonymous=True, reporter=reporter)
        assert "ck_report_anon_reporter" in str(excinfo.value)

        # Positive control 1: anonymous without reporter succeeds
        anon_report = ScamReportFactory(is_anonymous=True, reporter=None)
        assert anon_report.is_anonymous is True
        assert anon_report.reporter is None

        # Positive control 2: non-anonymous with reporter succeeds
        auth_report = ScamReportFactory(is_anonymous=False, reporter=reporter)
        assert auth_report.is_anonymous is False
        assert auth_report.reporter == reporter

    def test_negative_financial_loss_fails(self):
        """Failing-insert test for ck_report_financial_loss_non_negative."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReportFactory(financial_loss=Decimal("-0.01"))
        assert "ck_report_financial_loss_non_negative" in str(excinfo.value)

        # Positive control: non-negative financial loss succeeds
        valid_report = ScamReportFactory(financial_loss=Decimal("250.50"))
        assert valid_report.financial_loss == Decimal("250.50")

    def test_risk_score_above_100_fails(self):
        """Failing-insert test for ck_report_risk_score_range upper bound."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReportFactory(risk_score=101)
        assert "ck_report_risk_score_range" in str(excinfo.value)

        # Positive control: risk score 100 succeeds
        valid_report = ScamReportFactory(risk_score=100)
        assert valid_report.risk_score == 100

    def test_risk_score_below_0_fails(self):
        """Failing-insert test for ck_report_risk_score_range lower bound."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReportFactory(risk_score=-1)
        assert "ck_report_risk_score_range" in str(excinfo.value)

        # Positive control: risk score 0 succeeds
        valid_report = ScamReportFactory(risk_score=0)
        assert valid_report.risk_score == 0

    def test_message_text_exceeding_5000_chars_fails(self):
        """Failing-insert test for ck_report_message_text_length."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReportFactory(message_text="A" * 5001)
        assert "ck_report_message_text_length" in str(excinfo.value)

        # Positive control: exactly 5000 chars succeeds
        valid_report = ScamReportFactory(message_text="A" * 5000)
        assert len(valid_report.message_text) == 5000

    def test_invalid_scam_category_fails(self):
        """Failing-insert test for ck_report_category."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReport.objects.create(
                    reference_code="SCM-2026-CAT00001",
                    category="INVALID_CAT",
                    platform=Platform.WHATSAPP,
                    message_text="Scam text",
                    financial_loss=Decimal("0.00"),
                    currency="MYR",
                    country_code="MY",
                )
        assert "ck_report_category" in str(excinfo.value)

        # Positive control: valid category succeeds
        valid = ScamReportFactory(category=ScamCategory.ECOMMERCE_FRAUD)
        assert valid.category == ScamCategory.ECOMMERCE_FRAUD

    def test_invalid_platform_fails(self):
        """Failing-insert test for ck_report_platform."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReport.objects.create(
                    reference_code="SCM-2026-PLAT0001",
                    category=ScamCategory.PHISHING,
                    platform="UNKNOWN_APP",
                    message_text="Scam text",
                    financial_loss=Decimal("0.00"),
                    currency="MYR",
                    country_code="MY",
                )
        assert "ck_report_platform" in str(excinfo.value)

        # Positive control: valid platform succeeds
        valid = ScamReportFactory(platform=Platform.TELEGRAM)
        assert valid.platform == Platform.TELEGRAM

    def test_invalid_payment_method_fails(self):
        """Failing-insert test for ck_report_payment_method."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReport.objects.create(
                    reference_code="SCM-2026-PAYM0001",
                    category=ScamCategory.PHISHING,
                    platform=Platform.WHATSAPP,
                    payment_method="BARTER_TRADE",
                    message_text="Scam text",
                    financial_loss=Decimal("0.00"),
                    currency="MYR",
                    country_code="MY",
                )
        assert "ck_report_payment_method" in str(excinfo.value)

        # Positive control: valid payment_method succeeds
        valid = ScamReportFactory(payment_method=PaymentMethod.E_WALLET)
        assert valid.payment_method == PaymentMethod.E_WALLET

    def test_invalid_report_status_fails(self):
        """Failing-insert test for ck_report_status."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReport.objects.create(
                    reference_code="SCM-2026-STAT0001",
                    category=ScamCategory.PHISHING,
                    platform=Platform.WHATSAPP,
                    status="CLOSED",
                    message_text="Scam text",
                    financial_loss=Decimal("0.00"),
                    currency="MYR",
                    country_code="MY",
                )
        assert "ck_report_status" in str(excinfo.value)

        # Positive control: valid status succeeds
        valid = ScamReportFactory(status=ReportStatus.VERIFIED)
        assert valid.status == ReportStatus.VERIFIED

    def test_invalid_scan_status_fails(self):
        """Failing-insert test for ck_report_scan_status."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScamReport.objects.create(
                    reference_code="SCM-2026-SCAN0001",
                    category=ScamCategory.PHISHING,
                    platform=Platform.WHATSAPP,
                    scan_status="ANALYZING",
                    message_text="Scam text",
                    financial_loss=Decimal("0.00"),
                    currency="MYR",
                    country_code="MY",
                )
        assert "ck_report_scan_status" in str(excinfo.value)

        # Positive control: valid scan_status succeeds
        valid = ScamReportFactory(scan_status=ScanStatus.DONE)
        assert valid.scan_status == ScanStatus.DONE


@pytest.mark.django_db
class TestReportIndicatorConstraints:
    def test_duplicate_indicator_triple_fails(self):
        """Failing-insert test for uq_indicator_report_type_normalized."""
        report = ScamReportFactory()
        ReportIndicatorFactory(
            report=report,
            type=IndicatorType.PHONE,
            normalized_value="+60123456789",
        )

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ReportIndicator.objects.create(
                    report=report,
                    type=IndicatorType.PHONE,
                    raw_value="012-345 6789",
                    normalized_value="+60123456789",
                    display_value="+60•••••789",
                )
        assert "uq_indicator_report_type_normalized" in str(excinfo.value)

        # Positive control: different report or different type succeeds
        other_report = ScamReportFactory()
        other_indicator = ReportIndicatorFactory(
            report=other_report,
            type=IndicatorType.PHONE,
            normalized_value="+60123456789",
        )
        assert other_indicator.report == other_report

        diff_type = ReportIndicatorFactory(
            report=report,
            type=IndicatorType.URL,
            normalized_value="https://phish.example.com",
        )
        assert diff_type.type == IndicatorType.URL

    def test_invalid_indicator_type_fails(self):
        """Failing-insert test for ck_indicator_type."""
        report = ScamReportFactory()
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ReportIndicator.objects.create(
                    report=report,
                    type="INVALID",
                    raw_value="0x123",
                    normalized_value="0x123",
                    display_value="0x123",
                )
        assert "ck_indicator_type" in str(excinfo.value)

        # Positive control: valid indicator type succeeds
        valid = ReportIndicatorFactory(report=report, type=IndicatorType.EMAIL)
        assert valid.type == IndicatorType.EMAIL


@pytest.mark.django_db
class TestReportEvidenceConstraints:
    def test_duplicate_evidence_s3_key_fails(self):
        """Failing-insert test for unique s3_key."""
        key = "evidence/reports/shared-evidence-key.png"
        ReportEvidenceFactory(s3_key=key)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ReportEvidenceFactory(s3_key=key)
        assert "s3_key" in str(excinfo.value)

        # Positive control: distinct s3_key succeeds
        distinct = ReportEvidenceFactory(s3_key="evidence/reports/different-evidence-key.png")
        assert distinct.s3_key == "evidence/reports/different-evidence-key.png"

    def test_invalid_evidence_content_type_fails(self):
        """Failing-insert test for ck_evidence_content_type."""
        report = ScamReportFactory()
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ReportEvidence.objects.create(
                    report=report,
                    s3_key="evidence/invalid/archive.zip",
                    content_type="application/zip",
                    size_bytes=1024,
                    sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                )
        assert "ck_evidence_content_type" in str(excinfo.value)

        # Positive control: valid content type succeeds
        valid = ReportEvidenceFactory(content_type="application/pdf")
        assert valid.content_type == "application/pdf"

    def test_evidence_size_zero_or_negative_fails(self):
        """Failing-insert test for ck_evidence_size_bytes lower bound."""
        report = ScamReportFactory()
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ReportEvidence.objects.create(
                    report=report,
                    s3_key="evidence/invalid/empty.png",
                    content_type="image/png",
                    size_bytes=0,
                    sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                )
        assert "ck_evidence_size_bytes" in str(excinfo.value)

        # Positive control: size_bytes = 1 succeeds
        valid = ReportEvidenceFactory(size_bytes=1)
        assert valid.size_bytes == 1

    def test_evidence_size_exceeding_5mb_fails(self):
        """Failing-insert test for ck_evidence_size_bytes upper bound."""
        report = ScamReportFactory()
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ReportEvidence.objects.create(
                    report=report,
                    s3_key="evidence/invalid/too-large.png",
                    content_type="image/png",
                    size_bytes=5242881,
                    sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                )
        assert "ck_evidence_size_bytes" in str(excinfo.value)

        # Positive control: exactly 5242880 bytes succeeds
        valid = ReportEvidenceFactory(size_bytes=5242880)
        assert valid.size_bytes == 5242880


@pytest.mark.django_db
class TestRecoveryPlaybookConstraints:
    def test_invalid_playbook_category_fails(self):
        """Failing-insert test for ck_playbook_category."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                RecoveryPlaybook.objects.create(
                    category="PYRAMID_SCHEME",
                    title="Invalid Category Playbook",
                )
        assert "ck_playbook_category" in str(excinfo.value)

        # Positive control 1: valid category succeeds
        valid1 = RecoveryPlaybookFactory(category=ScamCategory.IMPERSONATION)
        assert valid1.category == ScamCategory.IMPERSONATION

        # Positive control 2: null category succeeds ("any" category)
        valid2 = RecoveryPlaybookFactory(category=None)
        assert valid2.category is None

    def test_invalid_playbook_payment_method_fails(self):
        """Failing-insert test for ck_playbook_payment_method."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                RecoveryPlaybook.objects.create(
                    payment_method="GOLD_COIN",
                    title="Invalid Payment Playbook",
                )
        assert "ck_playbook_payment_method" in str(excinfo.value)

        # Positive control 1: valid payment_method succeeds
        valid1 = RecoveryPlaybookFactory(payment_method=PaymentMethod.CARD)
        assert valid1.payment_method == PaymentMethod.CARD

        # Positive control 2: null payment_method succeeds ("any" payment method)
        valid2 = RecoveryPlaybookFactory(payment_method=None)
        assert valid2.payment_method is None


@pytest.mark.django_db
class TestBoundaryPasses:
    """Amendment E: boundary-pass tests for edge conditions."""

    def test_boundary_financial_loss_zero_ok(self):
        report = ScamReportFactory(financial_loss=Decimal("0.00"))
        assert report.financial_loss == Decimal("0.00")

    def test_boundary_risk_score_zero_ok(self):
        report = ScamReportFactory(risk_score=0)
        assert report.risk_score == 0

    def test_boundary_risk_score_one_hundred_ok(self):
        report = ScamReportFactory(risk_score=100)
        assert report.risk_score == 100

    def test_boundary_risk_score_null_ok(self):
        report = ScamReportFactory(risk_score=None)
        assert report.risk_score is None

    def test_boundary_message_text_exact_5000_chars_ok(self):
        text = "M" * 5000
        report = ScamReportFactory(message_text=text)
        assert len(report.message_text) == 5000

    def test_boundary_size_bytes_one_ok(self):
        evidence = ReportEvidenceFactory(size_bytes=1)
        assert evidence.size_bytes == 1

    def test_boundary_size_bytes_5242880_ok(self):
        evidence = ReportEvidenceFactory(size_bytes=5242880)
        assert evidence.size_bytes == 5242880


@pytest.mark.django_db
class TestRelationshipsAndPrivacy:
    def test_reporter_set_null_on_user_delete(self):
        reporter = UserFactory()
        report = ScamReportFactory(reporter=reporter, is_anonymous=False)
        assert report.reporter == reporter

        reporter.delete()
        report.refresh_from_db()
        assert report.reporter is None

    def test_reviewed_by_set_null_on_user_delete(self):
        analyst = UserFactory(role="ANALYST")
        report = ScamReportFactory(reviewed_by=analyst)
        assert report.reviewed_by == analyst

        analyst.delete()
        report.refresh_from_db()
        assert report.reviewed_by is None

    def test_report_cascade_deletes_indicators_and_evidence(self):
        report = ScamReportFactory()
        indicator = ReportIndicatorFactory(report=report)
        evidence = ReportEvidenceFactory(report=report)

        report_id = report.id
        indicator_id = indicator.id
        evidence_id = evidence.id

        report.delete()

        assert not ScamReport.objects.filter(id=report_id).exists()
        assert not ReportIndicator.objects.filter(id=indicator_id).exists()
        assert not ReportEvidence.objects.filter(id=evidence_id).exists()

    def test_verified_indicator_set_null_on_delete(self):
        from apps.intel.tests.factories import VerifiedIndicatorFactory

        vi = VerifiedIndicatorFactory()
        indicator = ReportIndicatorFactory(verified_indicator=vi)
        assert indicator.verified_indicator == vi

        vi.delete()
        indicator.refresh_from_db()
        assert indicator.verified_indicator is None

    def test_str_never_exposes_pii(self):
        report = ScamReportFactory(
            reference_code="SCM-2026-SEC00001",
            message_text="Confidential citizen message containing secret phone 0123456789",
        )
        report_str = str(report)
        assert "Confidential citizen message" not in report_str
        assert "0123456789" not in report_str
        assert "SCM-2026-SEC00001" in report_str

        indicator = ReportIndicatorFactory(
            report=report,
            type=IndicatorType.PHONE,
            raw_value="012-345 6789 (private citizen phone)",
        )
        ind_str = str(indicator)
        assert "private citizen phone" not in ind_str
        assert "PHONE" in ind_str

        evidence = ReportEvidenceFactory(
            report=report,
            s3_key="evidence/secret/path.png",
            sha256="abcdef1234567890",
        )
        ev_str = str(evidence)
        assert "evidence/secret/path.png" not in ev_str
        assert "abcdef1234567890" not in ev_str

        playbook = RecoveryPlaybookFactory(title="Standard Playbook")
        assert "Standard Playbook" in str(playbook)
