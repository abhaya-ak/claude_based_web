import logging
import random
import uuid

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core import aws
from apps.core.exceptions import ConflictError
from apps.literacy.models import (
    AttemptAnswer,
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


def submit_answer(
    attempt: SimulatorAttempt,
    scenario_id: uuid.UUID,
    answered_is_scam: bool,
    selected_flag_code: str | None = None,
) -> tuple[AttemptAnswer, SimulatorScenario, list[ScenarioRedFlag]]:
    """
    Submits and grades a player's answer for one scenario in an active attempt.
    Enforces attempt active status, scenario presence in attempt, and no-duplicate answer rule.
    Returns (answer, scenario, red_flags).
    """
    if attempt.status == AttemptStatus.COMPLETED:
        raise ConflictError(
            "Attempt is already completed and immutable.",
            code="attempt_already_completed",
        )

    scenario_uuid = uuid.UUID(str(scenario_id))
    attempt_uuids = [uuid.UUID(str(sid)) for sid in attempt.scenario_ids]
    if scenario_uuid not in attempt_uuids:
        raise ValidationError(
            {"scenario_id": ["Scenario does not belong to this simulation attempt."]},
            code="scenario_not_in_attempt",
        )

    # Check already answered (from annotation if present, else query)
    if getattr(attempt, "has_answered", None) is True:
        raise ConflictError(
            "Scenario has already been answered in this attempt.",
            code="already_answered",
        )
    if not hasattr(attempt, "has_answered"):
        if AttemptAnswer.objects.filter(attempt=attempt, scenario_id=scenario_uuid).exists():
            raise ConflictError(
                "Scenario has already been answered in this attempt.",
                code="already_answered",
            )

    # Fetch scenario and its red flags in 1 query for scam scenarios via select_related
    flags = list(ScenarioRedFlag.objects.filter(scenario_id=scenario_uuid).select_related("scenario"))
    if flags:
        scenario = flags[0].scenario
        scenario._prefetched_objects_cache = {"red_flags": flags}
    else:
        try:
            scenario = SimulatorScenario.objects.get(pk=scenario_uuid)
            scenario._prefetched_objects_cache = {"red_flags": []}
        except SimulatorScenario.DoesNotExist as exc:
            raise ValidationError(
                {"scenario_id": ["Scenario not found."]},
                code="scenario_not_found",
            ) from exc

    # Server-side grading matrix per D120
    if scenario.is_scam:
        if answered_is_scam:
            valid_flag_codes = {rf.flag_code for rf in flags}
            is_correct = bool(selected_flag_code and selected_flag_code in valid_flag_codes)
        else:
            is_correct = False
    else:
        if not answered_is_scam:
            is_correct = True
        else:
            is_correct = False

    # Enforce db constraint: flag only if answered_is_scam
    if not answered_is_scam:
        selected_flag_code = None

    answer = AttemptAnswer.objects.create(
        attempt=attempt,
        scenario=scenario,
        answered_is_scam=answered_is_scam,
        selected_flag_code=selected_flag_code,
        is_correct=is_correct,
    )

    return answer, scenario, flags


def complete_attempt(
    attempt: SimulatorAttempt,
    language: str = "en",
) -> tuple[SimulatorAttempt, QuerySet]:
    """
    Completes simulation attempt, validates 5 answers, calculates score,
    detects blind spots (tactics with >=2 misses per TO BE PROVEN #21),
    and attaches remediation guides per Contract §3.8.
    """
    if attempt.status == AttemptStatus.COMPLETED:
        raise ConflictError(
            "Attempt is already completed and immutable.",
            code="attempt_already_completed",
        )

    answers = list(attempt.answers.select_related("scenario"))
    if len(answers) < 5:
        raise ValidationError(
            {"attempt": [f"Attempt is incomplete: requires 5 answered scenarios before completion (has {len(answers)})."]},
            code="incomplete_attempt",
        )

    correct_count = sum(1 for a in answers if a.is_correct)
    score_pct = round((correct_count / 5.0) * 100)

    # Per-tactic profile and blind spots (tactics with >= 2 misses)
    tactics_stat = {}
    for ans in answers:
        sc = ans.scenario
        if not sc.is_scam or sc.tactic == ScenarioTactic.NONE.value:
            continue
        tac = sc.tactic
        if tac not in tactics_stat:
            tactics_stat[tac] = {"total": 0, "missed": 0, "is_blind_spot": False}
        tactics_stat[tac]["total"] += 1
        if not ans.is_correct:
            tactics_stat[tac]["missed"] += 1

    blind_spots = []
    for tac, stat in tactics_stat.items():
        if stat["missed"] >= 2:
            stat["is_blind_spot"] = True
            blind_spots.append(tac)

    profile = {
        "tactics": tactics_stat,
        "blind_spots": blind_spots,
    }

    # Contract §3.8 remediation guides
    from apps.literacy.selectors.guide_selectors import guides_for_tactics

    guides = guides_for_tactics(tactics=blind_spots, language=language)

    attempt.status = AttemptStatus.COMPLETED
    attempt.completed_at = timezone.now()
    attempt.score_pct = score_pct
    attempt.profile = profile
    attempt.save(update_fields=["status", "completed_at", "score_pct", "profile"])

    return attempt, guides
