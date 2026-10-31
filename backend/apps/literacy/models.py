import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models.functions import Length, Trim
from django.db.models.lookups import GreaterThanOrEqual

from apps.core.enums import AudienceGroup
from apps.core.models import TimeStampedModel


class Language(models.TextChoices):
    EN = "en", "English"
    NE = "ne", "Nepali"
    MS = "ms", "Malay"


class ReadabilityMode(models.TextChoices):
    STANDARD = "STANDARD", "Standard"
    LARGE_HIGH_CONTRAST = "LARGE_HIGH_CONTRAST", "Large & High Contrast"


class ContentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    ARCHIVED = "ARCHIVED", "Archived"


class AssetType(models.TextChoices):
    PDF = "PDF", "PDF Document"
    AUDIO = "AUDIO", "Audio"
    IMAGE = "IMAGE", "Image"


class Tactic(models.TextChoices):
    URGENCY = "URGENCY", "Urgency"
    AUTHORITY = "AUTHORITY", "Authority"
    FEAR = "FEAR", "Fear"
    GREED = "GREED", "Greed"


class EducationalGuide(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.CharField(max_length=200, unique=True)
    title = models.CharField(max_length=200)
    summary = models.CharField(max_length=500)
    body = models.TextField()
    audience_groups = ArrayField(
        models.CharField(max_length=15),
        default=list,
        blank=True,
    )
    tactics = ArrayField(
        models.CharField(max_length=10),
        default=list,
        blank=True,
    )
    language = models.CharField(
        max_length=2,
        choices=Language.choices,
        default=Language.EN,
    )
    readability_mode = models.CharField(
        max_length=20,
        choices=ReadabilityMode.choices,
        default=ReadabilityMode.STANDARD,
    )
    status = models.CharField(
        max_length=10,
        choices=ContentStatus.choices,
        default=ContentStatus.DRAFT,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_guides",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "literacy_educationalguide"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(language__in=Language.values),
                name="ck_guide_language",
            ),
            models.CheckConstraint(
                condition=models.Q(readability_mode__in=ReadabilityMode.values),
                name="ck_guide_readability_mode",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ContentStatus.values),
                name="ck_guide_status",
            ),
            models.CheckConstraint(
                condition=models.Q(audience_groups__contained_by=list(AudienceGroup.values)),
                name="ck_guide_audience_groups",
            ),
            models.CheckConstraint(
                condition=models.Q(tactics__contained_by=list(Tactic.values)),
                name="ck_guide_tactics",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status=ContentStatus.PUBLISHED)
                    | GreaterThanOrEqual(models.Func("audience_groups", function="CARDINALITY"), 1)
                ),
                name="ck_guide_published_audience",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status=ContentStatus.PUBLISHED)
                    | models.Q(published_at__isnull=False)
                ),
                name="ck_guide_published_timestamp",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "language", "-published_at"],
                name="idx_guide_list",
            ),
            GinIndex(
                fields=["audience_groups"],
                name="idx_guide_audience_gin",
            ),
            GinIndex(
                fields=["tactics"],
                name="idx_guide_tactics_gin",
            ),
        ]

    def __str__(self):
        # Privacy & safety: do not include body text
        return f"{self.title} ({self.slug})"


class GuideAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    guide = models.ForeignKey(
        "EducationalGuide",
        on_delete=models.CASCADE,
        related_name="assets",
    )
    asset_type = models.CharField(max_length=5, choices=AssetType.choices)
    s3_key = models.CharField(max_length=300, unique=True)
    content_type = models.CharField(max_length=60)
    size_bytes = models.IntegerField()
    duration_seconds = models.IntegerField(null=True, blank=True)
    alt_text = models.CharField(max_length=300, blank=True, default="")
    transcript = models.TextField(null=True, blank=True)
    sort_order = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "literacy_guideasset"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(asset_type__in=AssetType.values),
                name="ck_asset_type",
            ),
            models.CheckConstraint(
                condition=models.Q(size_bytes__gt=0),
                name="ck_asset_size_bytes_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(duration_seconds__isnull=True)
                    | models.Q(duration_seconds__gt=0)
                ),
                name="ck_asset_duration_positive",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(asset_type=AssetType.IMAGE)
                    | GreaterThanOrEqual(Length(Trim("alt_text")), 1)
                ),
                name="ck_asset_image_alt_text",
            ),
        ]

    def __str__(self):
        # Privacy & safety: do not include alt_text or transcript
        return f"Asset {self.asset_type} for guide {self.guide_id} ({self.s3_key})"
