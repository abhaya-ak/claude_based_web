import uuid
from decimal import Decimal

import factory

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


class ScamReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ScamReport

    reference_code = factory.Sequence(lambda n: f"SCM-2026-{n:08d}")
    client_submission_id = factory.LazyFunction(uuid.uuid4)
    reporter = None
    is_anonymous = False
    category = ScamCategory.PHISHING
    platform = Platform.WHATSAPP
    message_text = "Urgent: Your account is locked. Verify now at http://phish.example.com"
    financial_loss = Decimal("150.00")
    currency = "MYR"  # Set explicitly per Amendment B
    payment_method = PaymentMethod.BANK_TRANSFER
    country_code = "MY"
    admin_area = "Selangor"
    status = ReportStatus.PENDING
    risk_score = 45
    is_high_priority = False
    scan_status = ScanStatus.PENDING
    scan_attempts = 0


class ReportIndicatorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReportIndicator

    report = factory.SubFactory(ScamReportFactory)
    type = IndicatorType.PHONE
    raw_value = "+60123456789"
    normalized_value = factory.Sequence(lambda n: f"+6012345678{n}")
    display_value = "+60•••••789"


class ReportEvidenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReportEvidence

    report = factory.SubFactory(ScamReportFactory)
    s3_key = factory.Sequence(lambda n: f"evidence/test-{uuid.uuid4()}/evidence_{n}.png")
    content_type = "image/png"
    size_bytes = 2048
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class RecoveryPlaybookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RecoveryPlaybook

    category = ScamCategory.PHISHING
    payment_method = PaymentMethod.BANK_TRANSFER
    country_code = "MY"
    title = "Bank Transfer Phishing Recovery Playbook"
    steps = factory.LazyFunction(
        lambda: [
            {"title": "Contact Bank", "detail": "Call hotline immediately to freeze account"},
            {"title": "File Police Report", "detail": "Lodge report at nearest police station"},
        ]
    )
    hotlines = factory.LazyFunction(
        lambda: [
            {
                "name": "National Scam Response Centre (NSRC)",
                "number": "997",
                "url": "https://nfcc.my",
            }
        ]
    )
    priority = 10
    is_active = True
