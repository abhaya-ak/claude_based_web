import logging
import random
import uuid

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.core import aws
from apps.core.exceptions import ConflictError
from apps.literacy.models import (
    AttemptStatus,
    ScenarioRedFlag,
    ScenarioStatus,
    ScenarioTactic,
    SimulatorAttempt,
    SimulatorScenario,
)

logger = logging.getLogger(__name__)

MAX_SCENARIO_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def sniff_scenario_image(data: bytes) -> tuple[str, str]:
    """
    Sniffs whether bytes match PNG or JPEG magic bytes.
    Returns (content_type, extension).
    Raises ValidationError if unrecognized.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"

    raise ValidationError(
        {"image": ["Invalid image type. Only PNG and JPEG are accepted."]},
        code="invalid_file_type",
    )


def upload_scenario_image(file_obj) -> str:
    """Validates image magic bytes & size, uploads to S3 with SSE AES256, returns s3_key."""
    file_bytes = file_obj.read()
    if len(file_bytes) > MAX_SCENARIO_IMAGE_SIZE:
        raise ValidationError(
            {"image": [f"Image exceeds maximum size of {MAX_SCENARIO_IMAGE_SIZE // (1024 * 1024)} MB."]},
            code="file_too_large",
        )

    content_type, ext = sniff_scenario_image(file_bytes)
    s3_key = f"scenarios/{uuid.uuid4()}{ext}"
    bucket = getattr(settings, "MEDIA_BUCKET", "scamshield-media-dev")
    s3 = aws.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
        ServerSideEncryption="AES256",
    )
    return s3_key


def delete_s3_media_object(s3_key: str) -> None:
    """Failure-tolerant deletion of backing S3 media object."""
    if not s3_key:
        return
    bucket = getattr(settings, "MEDIA_BUCKET", "scamshield-media-dev")
    s3 = aws.client("s3")
    try:
        s3.delete_object(Bucket=bucket, Key=s3_key)
    except Exception as exc:
        logger.warning("Failed to delete S3 object %s: %s", s3_key, exc)


def create_scenario(data: dict, author, image_file=None) -> SimulatorScenario:
    """Creates a draft scenario with uploaded screenshot."""
    if not image_file:
        raise ValidationError({"image": ["Scenario image is required."]}, code="image_required")

    image_s3_key = upload_scenario_image(image_file)

    is_scam = data.get("is_scam")
    tactic = data.get("tactic")

    if is_scam is False and tactic != ScenarioTactic.NONE.value:
        raise ValidationError(
            {"tactic": ["Legitimate scenarios must have tactic 'NONE'."]},
            code="invalid_tactic",
        )
    if is_scam is True and tactic == ScenarioTactic.NONE.value:
        raise ValidationError(
            {"tactic": ["Scam scenarios must specify a tactic other than 'NONE'."]},
            code="invalid_tactic",
        )

    scenario = SimulatorScenario.objects.create(
        title=data["title"],
        channel=data["channel"],
        is_scam=is_scam,
        tactic=tactic,
        difficulty=data["difficulty"],
        image_s3_key=image_s3_key,
        image_alt=data["image_alt"],
        explanation=data["explanation"],
        status=ScenarioStatus.DRAFT,
        author=author,
    )
    return scenario


def update_scenario(scenario: SimulatorScenario, data: dict, image_file=None) -> SimulatorScenario:
    """Updates editable scenario fields."""
    if image_file:
        old_key = scenario.image_s3_key
        new_key = upload_scenario_image(image_file)
        scenario.image_s3_key = new_key
        delete_s3_media_object(old_key)

    is_scam = data.get("is_scam", scenario.is_scam)
    tactic = data.get("tactic", scenario.tactic)

    if is_scam is False and tactic != ScenarioTactic.NONE.value:
        raise ValidationError(
            {"tactic": ["Legitimate scenarios must have tactic 'NONE'."]},
            code="invalid_tactic",
        )
    if is_scam is True and tactic == ScenarioTactic.NONE.value:
        raise ValidationError(
            {"tactic": ["Scam scenarios must specify a tactic other than 'NONE'."]},
            code="invalid_tactic",
        )

    for field in ["title", "channel", "is_scam", "tactic", "difficulty", "image_alt", "explanation"]:
        if field in data:
            setattr(scenario, field, data[field])

    scenario.save()
    return scenario


def delete_scenario(scenario: SimulatorScenario) -> None:
    """Deletes scenario. If scenario has been answered in attempts, raises 409 Conflict per D118."""
    if scenario.answers.exists():
        raise ConflictError(
            "Scenario has been answered in attempts; archive it instead.",
            code="scenario_has_answers",
        )

    delete_s3_media_object(scenario.image_s3_key)
    scenario.delete()


def publish_scenario(scenario: SimulatorScenario) -> SimulatorScenario:
    """Publishes scenario enforcing red flag business rules."""
    flag_count = scenario.red_flags.count()
    if scenario.is_scam and flag_count < 1:
        raise ValidationError(
            {"red_flags": ["Scam scenario requires at least 1 red flag before publishing."]},
            code="red_flags_required",
        )
    if not scenario.is_scam and flag_count > 0:
        raise ValidationError(
            {"red_flags": ["Legitimate scenario cannot have red flags."]},
            code="legitimate_no_red_flags",
        )

    scenario.status = ScenarioStatus.PUBLISHED
    scenario.save(update_fields=["status", "updated_at"])
    return scenario


def unpublish_scenario(scenario: SimulatorScenario) -> SimulatorScenario:
    """Transitions scenario back to DRAFT."""
    scenario.status = ScenarioStatus.DRAFT
    scenario.save(update_fields=["status", "updated_at"])
    return scenario


def archive_scenario(scenario: SimulatorScenario) -> SimulatorScenario:
    """Transitions scenario to ARCHIVED."""
    scenario.status = ScenarioStatus.ARCHIVED
    scenario.save(update_fields=["status", "updated_at"])
    return scenario


def add_red_flag(scenario: SimulatorScenario, data: dict) -> ScenarioRedFlag:
    """Adds a red flag hotspot to a scam scenario."""
    if not scenario.is_scam:
        raise ValidationError(
            {"scenario": ["Cannot add red flags to a legitimate scenario."]},
            code="legitimate_no_red_flags",
        )

    return ScenarioRedFlag.objects.create(scenario=scenario, **data)


def delete_red_flag(flag: ScenarioRedFlag) -> None:
    """Deletes red flag hotspot."""
    flag.delete()


def start_attempt(user=None, session_key=None) -> tuple[SimulatorAttempt, list[SimulatorScenario]]:
    """
    Initializes a new simulator attempt by sampling 5 distinct published scenarios server-side.
    If fewer than 5 published scenarios exist, raises ConflictError (code="insufficient_scenarios").
    Assigns user or generates/preserves session_key for anonymous players.
    """
    published_qs = SimulatorScenario.objects.filter(status=ScenarioStatus.PUBLISHED)
    published_ids = list(published_qs.values_list("id", flat=True))

    if len(published_ids) < 5:
        raise ConflictError(
            "At least 5 published scenarios are required to start an attempt.",
            code="insufficient_scenarios",
        )

    sampled_ids = random.sample(published_ids, 5)

    if (not user or not user.is_authenticated) and not session_key:
        session_key = uuid.uuid4()

    attempt = SimulatorAttempt.objects.create(
        user=user if (user and user.is_authenticated) else None,
        session_key=session_key,
        scenario_ids=sampled_ids,
        status=AttemptStatus.IN_PROGRESS,
    )

    scenarios_by_id = {s.id: s for s in published_qs.filter(id__in=sampled_ids)}
    ordered_scenarios = [scenarios_by_id[sid] for sid in sampled_ids if sid in scenarios_by_id]

    return attempt, ordered_scenarios
