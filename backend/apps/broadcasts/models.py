import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Length
from django.db.models.lookups import LessThanOrEqual

from apps.core.enums import AudienceGroup
from apps.core.models import TimeStampedModel
from apps.reports.models import ScamCategory


class AdvisorySeverity(models.TextChoices):
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    CRITICAL = "CRITICAL", "Critical"


class AdvisoryStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    FAILED = "FAILED", "Failed"


class ThreatAdvisory(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    body = models.TextField()
    sms_text = models.CharField(max_length=140, null=True, blank=True)
    severity = models.CharField(max_length=8, choices=AdvisorySeverity.choices)
    target_audience = models.CharField(max_length=15)
    category = models.CharField(
        max_length=20, null=True, blank=True, choices=ScamCategory.choices
    )
    related_indicator = models.ForeignKey(
        "intel.VerifiedIndicator",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="threat_advisories",
    )
    status = models.CharField(
        max_length=10, choices=AdvisoryStatus.choices, default=AdvisoryStatus.DRAFT
    )
    sns_message_id = models.CharField(max_length=100, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_advisories",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="published_advisories",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "broadcasts_threatadvisory"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(severity__in=AdvisorySeverity.values),
                name="ck_adv_severity",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=AdvisoryStatus.values),
                name="ck_adv_status",
            ),
            models.CheckConstraint(
                condition=models.Q(target_audience="ALL")
                | models.Q(target_audience__in=AudienceGroup.values),
                name="ck_adv_target_audience",
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length("body"), 1500),
                name="ck_adv_body_length",
            ),
            models.CheckConstraint(
                condition=models.Q(category__isnull=True)
                | models.Q(category__in=ScamCategory.values),
                name="ck_adv_category",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "-published_at"],
                name="idx_adv_status_published",
            ),
        ]

    def __str__(self):
        return f"ThreatAdvisory({self.id}, title={self.title}, severity={self.severity})"
