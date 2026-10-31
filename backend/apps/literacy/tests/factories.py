import uuid
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.core.enums import AudienceGroup
from apps.literacy.models import (
    AssetType,
    AttemptAnswer,
    AttemptStatus,
    ContentStatus,
    EducationalGuide,
    GuideAsset,
    Language,
    ReadabilityMode,
    RedFlagCode,
    ScenarioChannel,
    ScenarioRedFlag,
    ScenarioStatus,
    ScenarioTactic,
    SimulatorAttempt,
    SimulatorScenario,
    Tactic,
)


class EducationalGuideFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EducationalGuide

    slug = factory.Sequence(lambda n: f"how-to-spot-scams-{n}")
    title = factory.Sequence(lambda n: f"Guide #{n}: How to Spot Common Scams")
    summary = "A comprehensive overview of common online scam tactics and protection steps."
    body = "# Recognizing Scams\n\nAlways verify the sender domain before clicking links."
    audience_groups = factory.LazyFunction(lambda: [AudienceGroup.GENERAL.value])
    tactics = factory.LazyFunction(lambda: [Tactic.URGENCY.value])
    language = Language.EN
    readability_mode = ReadabilityMode.STANDARD
    status = ContentStatus.DRAFT
    author = factory.SubFactory(UserFactory, role="EDUCATOR")
    published_at = None


class GuideAssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GuideAsset

    guide = factory.SubFactory(EducationalGuideFactory)
    asset_type = AssetType.IMAGE
    s3_key = factory.Sequence(lambda n: f"guides/test-guide/asset-{n}.png")
    content_type = "image/png"
    size_bytes = 102400
    duration_seconds = None
    alt_text = "Screenshot illustrating mismatched sender email domain"
    transcript = None
    sort_order = 0


class SimulatorScenarioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SimulatorScenario

    title = factory.Sequence(lambda n: f"Scenario #{n}: Suspicious Delivery SMS")
    channel = ScenarioChannel.SMS
    is_scam = True
    tactic = ScenarioTactic.URGENCY
    difficulty = 1
    image_s3_key = factory.Sequence(lambda n: f"scenarios/scenario-{n}.png")
    image_alt = "Fake parcel delivery notice urging immediate fee payment"
    explanation = "Legitimate couriers do not ask for delivery fees via short SMS links."
    status = ScenarioStatus.DRAFT
    author = factory.SubFactory(UserFactory, role="EDUCATOR")


class ScenarioRedFlagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ScenarioRedFlag

    scenario = factory.SubFactory(SimulatorScenarioFactory)
    flag_code = RedFlagCode.SUSPICIOUS_LINK
    x_pct = Decimal("10.00")
    y_pct = Decimal("20.00")
    w_pct = Decimal("30.00")
    h_pct = Decimal("15.00")
    explanation = "The URL uses a misleading domain disguised as a genuine service."


class SimulatorAttemptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SimulatorAttempt

    user = factory.SubFactory(UserFactory, role="CITIZEN")
    session_key = None
    status = AttemptStatus.IN_PROGRESS
    scenario_ids = factory.LazyFunction(lambda: [uuid.uuid4() for _ in range(5)])
    score_pct = None
    profile = None
    started_at = factory.LazyFunction(timezone.now)
    completed_at = None


class AttemptAnswerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AttemptAnswer

    attempt = factory.SubFactory(SimulatorAttemptFactory)
    scenario = factory.SubFactory(SimulatorScenarioFactory)
    answered_is_scam = True
    selected_flag_code = RedFlagCode.SUSPICIOUS_LINK
    is_correct = True

