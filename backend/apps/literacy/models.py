import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models.functions import Length, Trim
from django.db.models.lookups import Exact, GreaterThanOrEqual, LessThanOrEqual
from django.utils import timezone

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


class ScenarioChannel(models.TextChoices):
    SMS = "SMS", "SMS"
    EMAIL = "EMAIL", "Email"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    WEBSITE = "WEBSITE", "Website"
    SOCIAL = "SOCIAL", "Social Media"


class ScenarioStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    ARCHIVED = "ARCHIVED", "Archived"


class ScenarioTactic(models.TextChoices):
    URGENCY = Tactic.URGENCY.value, Tactic.URGENCY.label
    AUTHORITY = Tactic.AUTHORITY.value, Tactic.AUTHORITY.label
    FEAR = Tactic.FEAR.value, Tactic.FEAR.label
    GREED = Tactic.GREED.value, Tactic.GREED.label
    NONE = "NONE", "None"


class RedFlagCode(models.TextChoices):
    MISMATCHED_DOMAIN = "MISMATCHED_DOMAIN", "Mismatched Domain"
    ARTIFICIAL_URGENCY = "ARTIFICIAL_URGENCY", "Artificial Urgency"
    AUTHORITY_IMPERSONATION = "AUTHORITY_IMPERSONATION", "Authority Impersonation"
    THREAT_OF_LOSS = "THREAT_OF_LOSS", "Threat of Loss"
    TOO_GOOD_TO_BE_TRUE = "TOO_GOOD_TO_BE_TRUE", "Too Good to Be True"
    REQUEST_FOR_SENSITIVE_DATA = "REQUEST_FOR_SENSITIVE_DATA", "Request for Sensitive Data"
    SUSPICIOUS_LINK = "SUSPICIOUS_LINK", "Suspicious Link"
    POOR_GRAMMAR = "POOR_GRAMMAR", "Poor Grammar"
    OTHER = "OTHER", "Other"


class AttemptStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED = "COMPLETED", "Completed"


class SimulatorScenario(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    channel = models.CharField(max_length=10, choices=ScenarioChannel.choices)
    is_scam = models.BooleanField()
    tactic = models.CharField(max_length=10, choices=ScenarioTactic.choices)
    difficulty = models.SmallIntegerField()
    image_s3_key = models.CharField(max_length=300)
    image_alt = models.CharField(max_length=300)
    explanation = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=ScenarioStatus.choices,
        default=ScenarioStatus.DRAFT,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_scenarios",
    )

    class Meta:
        db_table = "literacy_simulatorscenario"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(channel__in=ScenarioChannel.values),
                name="ck_scenario_channel",
            ),
            models.CheckConstraint(
                condition=models.Q(tactic__in=ScenarioTactic.values),
                name="ck_scenario_tactic",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ScenarioStatus.values),
                name="ck_scenario_status",
            ),
            models.CheckConstraint(
                condition=models.Q(difficulty__gte=1, difficulty__lte=3),
                name="ck_scenario_difficulty",
            ),
            models.CheckConstraint(
                condition=(models.Q(is_scam=True) | models.Q(tactic=ScenarioTactic.NONE)),
                name="ck_scenario_legit_tactic_none",
            ),
            models.CheckConstraint(
                condition=(~models.Q(is_scam=True) | ~models.Q(tactic=ScenarioTactic.NONE)),
                name="ck_scenario_scam_has_tactic",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="idx_scn_status"),
        ]

    def __str__(self):
        # Privacy & safety: do not include explanation or image_alt
        return f"Scenario {self.id}: {self.title} ({self.channel})"


class ScenarioRedFlag(models.Model):
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(
        "SimulatorScenario",
        on_delete=models.CASCADE,
        related_name="red_flags",
    )
    flag_code = models.CharField(max_length=30, choices=RedFlagCode.choices)
    x_pct = models.DecimalField(max_digits=5, decimal_places=2)
    y_pct = models.DecimalField(max_digits=5, decimal_places=2)
    w_pct = models.DecimalField(max_digits=5, decimal_places=2)
    h_pct = models.DecimalField(max_digits=5, decimal_places=2)
    explanation = models.CharField(max_length=300)

    class Meta:
        db_table = "literacy_scenarioredflag"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(flag_code__in=RedFlagCode.values),
                name="ck_flag_code",
            ),
            models.CheckConstraint(
                condition=models.Q(x_pct__gte=0, x_pct__lte=100),
                name="ck_flag_x_pct_range",
            ),
            models.CheckConstraint(
                condition=models.Q(y_pct__gte=0, y_pct__lte=100),
                name="ck_flag_y_pct_range",
            ),
            models.CheckConstraint(
                condition=models.Q(w_pct__gt=0, w_pct__lte=100),
                name="ck_flag_w_pct_range",
            ),
            models.CheckConstraint(
                condition=models.Q(h_pct__gt=0, h_pct__lte=100),
                name="ck_flag_h_pct_range",
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(models.F("x_pct") + models.F("w_pct"), 100),
                name="ck_flag_x_plus_w_bound",
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(models.F("y_pct") + models.F("h_pct"), 100),
                name="ck_flag_y_plus_h_bound",
            ),
        ]

    def __str__(self):
        # Privacy & safety: do not include explanation
        return f"RedFlag {self.flag_code} on scenario {self.scenario_id}"


class SimulatorAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="simulator_attempts",
        db_index=False,
    )
    session_key = models.UUIDField(null=True, blank=True)
    status = models.CharField(
        max_length=12,
        choices=AttemptStatus.choices,
        default=AttemptStatus.IN_PROGRESS,
    )
    scenario_ids = ArrayField(models.UUIDField())
    score_pct = models.SmallIntegerField(null=True, blank=True)
    profile = models.JSONField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "literacy_simulatorattempt"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(user__isnull=False) | models.Q(session_key__isnull=False),
                name="ck_attempt_user_or_session",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=AttemptStatus.values),
                name="ck_attempt_status",
            ),
            models.CheckConstraint(
                condition=models.Q(score_pct__isnull=True)
                | models.Q(score_pct__gte=0, score_pct__lte=100),
                name="ck_attempt_score_pct_range",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status=AttemptStatus.COMPLETED)
                    | (models.Q(completed_at__isnull=False) & models.Q(score_pct__isnull=False))
                ),
                name="ck_attempt_completed_fields",
            ),
            models.CheckConstraint(
                condition=Exact(models.Func("scenario_ids", function="CARDINALITY"), 5),
                name="ck_attempt_scenario_count",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-started_at"], name="idx_attempt_user"),
        ]

    def __str__(self):
        # Privacy & safety: do not include profile or session_key
        return f"Attempt {self.id} ({self.status})"


class AttemptAnswer(models.Model):
    id = models.BigAutoField(primary_key=True)
    attempt = models.ForeignKey(
        "SimulatorAttempt",
        on_delete=models.CASCADE,
        related_name="answers",
        db_index=False,
    )
    scenario = models.ForeignKey(
        "SimulatorScenario",
        on_delete=models.PROTECT,
        related_name="answers",
    )
    answered_is_scam = models.BooleanField()
    selected_flag_code = models.CharField(
        max_length=30,
        choices=RedFlagCode.choices,
        null=True,
        blank=True,
    )
    is_correct = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "literacy_attemptanswer"
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "scenario"],
                name="uq_answer_attempt_scenario",
            ),
            models.CheckConstraint(
                condition=models.Q(selected_flag_code__isnull=True)
                | models.Q(selected_flag_code__in=RedFlagCode.values),
                name="ck_answer_selected_flag_code",
            ),
            models.CheckConstraint(
                condition=models.Q(answered_is_scam=True) | models.Q(selected_flag_code__isnull=True),
                name="ck_answer_flag_only_if_scam",
            ),
        ]

    def __str__(self):
        # Privacy & safety: do not include selected_flag_code or is_correct
        return f"Answer {self.id} for attempt {self.attempt_id}"

