import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Length, Trim
from django.db.models.lookups import GreaterThanOrEqual

from apps.core.models import TimeStampedModel


class IndicatorType(models.TextChoices):
    PHONE = "PHONE", "Phone"
    URL = "URL", "URL"
    DOMAIN = "DOMAIN", "Domain"
    EMAIL = "EMAIL", "Email"
    BANK_ACCOUNT = "BANK_ACCOUNT", "Bank Account"


class ScamCategory(models.TextChoices):
    PHISHING = "PHISHING", "Phishing"
    FAKE_JOB = "FAKE_JOB", "Fake Job"
    ECOMMERCE_FRAUD = "ECOMMERCE_FRAUD", "E-commerce Fraud"
    IMPERSONATION = "IMPERSONATION", "Impersonation"
    OTHER = "OTHER", "Other"


class ThreatLevel(models.TextChoices):
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class IndicatorStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REVOKED = "REVOKED", "Revoked"


class TriageAction(models.TextChoices):
    VERIFY = "VERIFY", "Verify"
    REJECT = "REJECT", "Reject"


class VerifiedIndicator(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=12, choices=IndicatorType.choices)
    normalized_value = models.CharField(max_length=512)
    display_value = models.CharField(max_length=128)
    primary_category = models.CharField(max_length=20, choices=ScamCategory.choices)
    threat_level = models.CharField(max_length=10, choices=ThreatLevel.choices)
    total_report_count = models.IntegerField()  # NO default per Amendment B
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    status = models.CharField(
        max_length=8, choices=IndicatorStatus.choices, default=IndicatorStatus.ACTIVE
    )
    public_note = models.CharField(
        max_length=500, blank=True, default=""
    )  # NOT NULL per Amendment C
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_indicators",
    )
    verified_at = models.DateTimeField()
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_indicators",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=300, null=True, blank=True)

    class Meta:
        db_table = "intel_verifiedindicator"
        constraints = [
            models.UniqueConstraint(
                fields=["type", "normalized_value"],
                name="uq_vi_type_normalized_val",
            ),
            models.CheckConstraint(
                condition=models.Q(type__in=IndicatorType.values),
                name="ck_vi_type",
            ),
            models.CheckConstraint(
                condition=models.Q(threat_level__in=ThreatLevel.values),
                name="ck_vi_threat_level",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=IndicatorStatus.values),
                name="ck_vi_status",
            ),
            models.CheckConstraint(
                condition=models.Q(total_report_count__gte=1),
                name="ck_vi_total_report_count",
            ),
            models.CheckConstraint(
                condition=models.Q(primary_category__in=ScamCategory.values),
                name="ck_vi_primary_category",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "threat_level"],
                name="idx_vi_status_level",
            ),
            models.Index(
                fields=["-last_seen_at"],
                name="idx_vi_last_seen",
            ),
        ]

    def __str__(self):
        return f"VerifiedIndicator({self.id}, type={self.type}, threat={self.threat_level})"


class TriageDecision(models.Model):
    id = models.BigAutoField(primary_key=True)
    report = models.ForeignKey(
        "reports.ScamReport",
        on_delete=models.CASCADE,
        related_name="triage_decisions",
    )
    analyst = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="triage_decisions",
    )
    action = models.CharField(max_length=8, choices=TriageAction.choices)
    indicator = models.ForeignKey(
        VerifiedIndicator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triage_decisions",
    )
    reason = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "intel_triagedecision"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action__in=TriageAction.values),
                name="ck_triage_action",
            ),
            models.CheckConstraint(
                condition=~models.Q(action=TriageAction.REJECT)
                | (
                    models.Q(reason__isnull=False)
                    & GreaterThanOrEqual(Length(Trim("reason")), 1)
                ),
                name="ck_triage_reject_reason",
            ),
        ]

    def __str__(self):
        return f"TriageDecision({self.id}, action={self.action})"
