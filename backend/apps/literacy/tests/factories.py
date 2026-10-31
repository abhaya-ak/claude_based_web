import factory

from apps.accounts.tests.factories import UserFactory
from apps.core.enums import AudienceGroup
from apps.literacy.models import (
    AssetType,
    ContentStatus,
    EducationalGuide,
    GuideAsset,
    Language,
    ReadabilityMode,
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
