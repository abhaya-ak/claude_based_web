import pytest
from django.utils import timezone

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.enums import AudienceGroup
from apps.literacy.models import AssetType, ContentStatus, EducationalGuide, GuideAsset, Language, Tactic
from apps.literacy.selectors import guides_for_tactics


@pytest.fixture
def educator(db):
    return User.objects.create_user(
        email="educator_selector@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def sample_guides(educator):
    now = timezone.now()

    # 1. Published, English, URGENCY + FEAR
    g1 = EducationalGuide.objects.create(
        slug="urgent-threats-en",
        title="Urgent Bank Threat Scams",
        summary="How to handle urgent threats claiming police arrest.",
        body="Scammers threaten arrest. Do not panic.",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.URGENCY.value, Tactic.FEAR.value],
        language=Language.EN.value,
        status=ContentStatus.PUBLISHED.value,
        author=educator,
        published_at=now,
    )
    # Assets for g1 in reverse sort_order to verify prefetch ordering
    GuideAsset.objects.create(
        guide=g1,
        asset_type=AssetType.IMAGE.value,
        s3_key=f"guides/{g1.id}/asset-2.png",
        content_type="image/png",
        size_bytes=50000,
        alt_text="Second asset",
        sort_order=2,
    )
    GuideAsset.objects.create(
        guide=g1,
        asset_type=AssetType.IMAGE.value,
        s3_key=f"guides/{g1.id}/asset-1.png",
        content_type="image/png",
        size_bytes=40000,
        alt_text="First asset",
        sort_order=1,
    )

    # 2. Published, English, GREED only
    g2 = EducationalGuide.objects.create(
        slug="crypto-greed-en",
        title="Crypto Investment Schemes",
        summary="High returns guaranteed are always scams.",
        body="Never invest in unregistered platforms.",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.GREED.value],
        language=Language.EN.value,
        status=ContentStatus.PUBLISHED.value,
        author=educator,
        published_at=now,
    )

    # 3. Draft, English, URGENCY (must not be returned!)
    EducationalGuide.objects.create(
        slug="draft-urgent-en",
        title="Draft Urgent Guide",
        summary="Draft summary.",
        body="Draft body.",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.URGENCY.value],
        language=Language.EN.value,
        status=ContentStatus.DRAFT.value,
        author=educator,
    )

    # 4. Archived, English, URGENCY (must not be returned!)
    EducationalGuide.objects.create(
        slug="archived-urgent-en",
        title="Archived Urgent Guide",
        summary="Archived summary.",
        body="Archived body.",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.URGENCY.value],
        language=Language.EN.value,
        status=ContentStatus.ARCHIVED.value,
        author=educator,
    )

    # 5. Published, Nepali, URGENCY
    g5 = EducationalGuide.objects.create(
        slug="urgent-threats-ne",
        title="आपतकालीन फोन घोटाला",
        summary="आपतकालीन फोन घोटालाबाट कसरी बच्ने।",
        body="डराउनु पर्दैन।",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.URGENCY.value],
        language=Language.NE.value,
        status=ContentStatus.PUBLISHED.value,
        author=educator,
        published_at=now,
    )

    return {"g1": g1, "g2": g2, "g5": g5}


@pytest.mark.django_db
class TestGuidesForTacticsSelector:
    """Contract §3.8: literacy.selectors.guides_for_tactics"""

    def test_guides_for_tactics_matches_overlap_and_filters_status(self, sample_guides):
        # Querying URGENCY in English should return only g1 (published), NOT g3 (draft) or g4 (archived)
        qs = guides_for_tactics(["URGENCY"], language="en")
        guide_ids = list(qs.values_list("id", flat=True))

        assert sample_guides["g1"].id in guide_ids
        assert sample_guides["g2"].id not in guide_ids
        assert sample_guides["g5"].id not in guide_ids
        assert qs.count() == 1

    def test_guides_for_tactics_multiple_tactics_overlap(self, sample_guides):
        # Querying URGENCY and GREED should return g1 (has URGENCY) and g2 (has GREED)
        qs = guides_for_tactics(["URGENCY", "GREED"], language="en")
        guide_ids = set(qs.values_list("id", flat=True))

        assert guide_ids == {sample_guides["g1"].id, sample_guides["g2"].id}

    def test_guides_for_tactics_language_isolation(self, sample_guides):
        # Querying URGENCY in Nepali should return only g5
        qs = guides_for_tactics(["URGENCY"], language="ne")
        assert list(qs.values_list("id", flat=True)) == [sample_guides["g5"].id]

    def test_guides_for_tactics_empty_tactics_returns_empty_queryset(self, sample_guides):
        qs = guides_for_tactics([], language="en")
        assert qs.count() == 0

    def test_guides_for_tactics_prefetches_ordered_assets(self, sample_guides, django_assert_max_num_queries):
        # Must prefetch assets in sort_order (1 then 2) without extra queries during iteration
        with django_assert_max_num_queries(2):  # 1 for guides, 1 for prefetched assets
            qs = guides_for_tactics(["URGENCY"], language="en")
            guides = list(qs)
            assert len(guides) == 1
            assets = list(guides[0].assets.all())
            assert len(assets) == 2
            assert assets[0].sort_order == 1
            assert assets[1].sort_order == 2
