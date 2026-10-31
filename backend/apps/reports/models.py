import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models.functions import Length
from django.db.models.lookups import LessThanOrEqual

from apps.core.models import TimeStampedModel


class ScamCategory(models.TextChoices):
    PHISHING = "PHISHING", "Phishing"
    FAKE_JOB = "FAKE_JOB", "Fake Job"
    ECOMMERCE_FRAUD = "ECOMMERCE_FRAUD", "E-commerce Fraud"
    IMPERSONATION = "IMPERSONATION", "Impersonation"
    OTHER = "OTHER", "Other"


class Platform(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"
    TELEGRAM = "TELEGRAM", "Telegram"
    FACEBOOK = "FACEBOOK", "Facebook"
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"
    WEBSITE = "WEBSITE", "Website"
    OTHER = "OTHER", "Other"


class IndicatorType(models.TextChoices):
    PHONE = "PHONE", "Phone"
    URL = "URL", "URL"
    DOMAIN = "DOMAIN", "Domain"
    EMAIL = "EMAIL", "Email"
    BANK_ACCOUNT = "BANK_ACCOUNT", "Bank Account"


class PaymentMethod(models.TextChoices):
    NONE = "NONE", "None"
    BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
    E_WALLET = "E_WALLET", "E-Wallet"
    CARD = "CARD", "Card"
    CRYPTO = "CRYPTO", "Crypto"
    CASH = "CASH", "Cash"
    OTHER = "OTHER", "Other"


class ReportStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"


class ScanStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    DONE = "DONE", "Done"
    FAILED = "FAILED", "Failed"


class ScamReport(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_code = models.CharField(max_length=24, unique=True)
    client_submission_id = models.UUIDField(unique=True, null=True, blank=True)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filed_reports",
    )
    is_anonymous = models.BooleanField(default=False)
    access_key_hash = models.CharField(max_length=128, null=True, blank=True)
    category = models.CharField(max_length=20, choices=ScamCategory.choices)
    platform = models.CharField(max_length=12, choices=Platform.choices)
    message_text = models.TextField()
    financial_loss = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3)
    payment_method = models.CharField(
        max_length=15, choices=PaymentMethod.choices, default=PaymentMethod.NONE
    )
    country_code = models.CharField(max_length=2)
    admin_area = models.CharField(max_length=100, null=True, blank=True)
    incident_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=ReportStatus.choices, default=ReportStatus.PENDING
    )
    risk_score = models.SmallIntegerField(null=True, blank=True)
    is_high_priority = models.BooleanField(default=False)
    scan_status = models.CharField(
        max_length=10, choices=ScanStatus.choices, default=ScanStatus.PENDING
    )
    scan_attempts = models.SmallIntegerField(default=0)
    scan_dispatched_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = "reports_scamreport"
        constraints = [
            models.CheckConstraint(
                condition=~(models.Q(is_anonymous=True) & models.Q(reporter__isnull=False)),
                name="ck_report_anon_reporter",
            ),
            models.CheckConstraint(
                condition=models.Q(financial_loss__gte=0),
                name="ck_report_financial_loss_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(risk_score__isnull=True)
                | models.Q(risk_score__range=(0, 100)),
                name="ck_report_risk_score_range",
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length("message_text"), 5000),
                name="ck_report_message_text_length",
            ),
            models.CheckConstraint(
                condition=models.Q(category__in=ScamCategory.values),
                name="ck_report_category",
            ),
            models.CheckConstraint(
                condition=models.Q(platform__in=Platform.values),
                name="ck_report_platform",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_method__in=PaymentMethod.values),
                name="ck_report_payment_method",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ReportStatus.values),
                name="ck_report_status",
            ),
            models.CheckConstraint(
                condition=models.Q(scan_status__in=ScanStatus.values),
                name="ck_report_scan_status",
            ),
        ]
        indexes = [
            models.Index(
                models.F("risk_score").desc(nulls_last=True),
                models.F("created_at").asc(),
                name="idx_report_queue",
                condition=models.Q(status=ReportStatus.PENDING),
            ),
            models.Index(
                fields=["status", "-created_at"],
                name="idx_report_status_created",
            ),
            models.Index(
                fields=["created_at"],
                name="idx_report_created",
            ),
            models.Index(
                fields=["platform", "category", "created_at"],
                name="idx_report_plat_cat_created",
            ),
            models.Index(
                fields=["country_code", "admin_area", "created_at"],
                name="idx_report_geo_created",
            ),
            models.Index(
                fields=["reporter", "-created_at"],
                name="idx_report_reporter",
                condition=models.Q(reporter__isnull=False),
            ),
            models.Index(
                fields=["scan_dispatched_at"],
                name="idx_report_scan_pending",
                condition=models.Q(scan_status=ScanStatus.PENDING),
            ),
        ]

    def __str__(self):
        return f"ScamReport({self.id}, ref={self.reference_code}, status={self.status})"


class ReportIndicator(models.Model):
    id = models.BigAutoField(primary_key=True)
    report = models.ForeignKey(
        ScamReport,
        on_delete=models.CASCADE,
        related_name="indicators",
    )
    type = models.CharField(max_length=12, choices=IndicatorType.choices)
    raw_value = models.CharField(max_length=512)
    normalized_value = models.CharField(max_length=512)
    display_value = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reports_reportindicator"
        constraints = [
            models.UniqueConstraint(
                fields=["report", "type", "normalized_value"],
                name="uq_indicator_report_type_normalized",
            ),
            models.CheckConstraint(
                condition=models.Q(type__in=IndicatorType.values),
                name="ck_indicator_type",
            ),
        ]
        indexes = [
            models.Index(
                fields=["type", "normalized_value"],
                name="idx_ri_type_value",
            ),
        ]

    def __str__(self):
        return f"ReportIndicator({self.id}, type={self.type})"


class ReportEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        ScamReport,
        on_delete=models.CASCADE,
        related_name="evidence",
    )
    s3_key = models.CharField(max_length=300, unique=True)
    content_type = models.CharField(max_length=40)
    size_bytes = models.IntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reports_reportevidence"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    content_type__in=["image/png", "image/jpeg", "application/pdf"]
                ),
                name="ck_evidence_content_type",
            ),
            models.CheckConstraint(
                condition=models.Q(size_bytes__gte=1, size_bytes__lte=5242880),
                name="ck_evidence_size_bytes",
            ),
        ]

    def __str__(self):
        return f"ReportEvidence({self.id}, content_type={self.content_type})"


class RecoveryPlaybook(models.Model):
    id = models.BigAutoField(primary_key=True)
    category = models.CharField(
        max_length=20, null=True, blank=True, choices=ScamCategory.choices
    )
    payment_method = models.CharField(
        max_length=15, null=True, blank=True, choices=PaymentMethod.choices
    )
    country_code = models.CharField(max_length=2, null=True, blank=True)
    title = models.CharField(max_length=150)
    steps = models.JSONField(default=list)
    hotlines = models.JSONField(default=list)
    priority = models.SmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reports_recoveryplaybook"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(category__isnull=True)
                | models.Q(category__in=ScamCategory.values),
                name="ck_playbook_category",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_method__isnull=True)
                | models.Q(payment_method__in=PaymentMethod.values),
                name="ck_playbook_payment_method",
            ),
        ]

    def __str__(self):
        return f"RecoveryPlaybook({self.id}, title={self.title})"
