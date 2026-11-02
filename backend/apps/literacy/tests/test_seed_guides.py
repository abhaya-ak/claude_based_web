import pytest
from django.core.management import call_command

from apps.core.enums import AudienceGroup
from apps.literacy.models import ContentStatus, EducationalGuide, Language, Tactic


@pytest.mark.django_db
class TestSeedGuidesCommand:
    def test_seed_guides_populates_multilingual_curriculum_idempotently(self):
        # 1. First run seeds curriculum
        call_command("seed_guides")

        guides = EducationalGuide.objects.all()
        assert guides.count() >= 3

        # Confirm all are PUBLISHED and have published_at
        for g in guides:
            assert g.status == ContentStatus.PUBLISHED.value
            assert g.published_at is not None
            assert len(g.audience_groups) >= 1
            assert len(g.tactics) >= 1

        # Check languages present
        languages = set(guides.values_list("language", flat=True))
        assert Language.EN.value in languages
        assert Language.NE.value in languages
        assert Language.MS.value in languages

        # Check elderly audience is covered
        elderly_guides = EducationalGuide.objects.filter(
            audience_groups__contains=[AudienceGroup.ELDERLY.value]
        )
        assert elderly_guides.exists()

        # Check core tactics are covered
        urgency_guides = EducationalGuide.objects.filter(
            tactics__contains=[Tactic.URGENCY.value]
        )
        assert urgency_guides.exists()

        initial_count = guides.count()

        # 2. Second run is strictly idempotent
        call_command("seed_guides")
        assert EducationalGuide.objects.count() == initial_count
