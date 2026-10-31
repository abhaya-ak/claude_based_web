import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

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
from apps.literacy.tests.factories import EducationalGuideFactory, GuideAssetFactory


@pytest.mark.django_db
class TestEducationalGuideConstraints:
    def test_duplicate_slug_fails(self):
        """Failing-insert test for unique slug."""
        EducationalGuideFactory(slug="scam-prevention-tips")
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(slug="scam-prevention-tips")
        assert "slug" in str(excinfo.value)

        # Positive control: distinct slug succeeds
        guide2 = EducationalGuideFactory(slug="different-scam-tips")
        assert guide2.slug == "different-scam-tips"

    def test_invalid_language_fails(self):
        """Failing-insert test for ck_guide_language."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(language="fr")
        assert "ck_guide_language" in str(excinfo.value)

        # Positive control: valid languages succeed
        valid_en = EducationalGuideFactory(language=Language.EN)
        valid_ne = EducationalGuideFactory(language=Language.NE)
        valid_ms = EducationalGuideFactory(language=Language.MS)
        assert valid_en.language == Language.EN
        assert valid_ne.language == Language.NE
        assert valid_ms.language == Language.MS

    def test_invalid_readability_mode_fails(self):
        """Failing-insert test for ck_guide_readability_mode."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(readability_mode="COMPACT")
        assert "ck_guide_readability_mode" in str(excinfo.value)

        # Positive control: valid readability mode succeeds
        valid = EducationalGuideFactory(readability_mode=ReadabilityMode.LARGE_HIGH_CONTRAST)
        assert valid.readability_mode == ReadabilityMode.LARGE_HIGH_CONTRAST

    def test_invalid_status_fails(self):
        """Failing-insert test for ck_guide_status."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(status="IN_REVIEW")
        assert "ck_guide_status" in str(excinfo.value)

        # Positive control: valid status succeeds
        valid = EducationalGuideFactory(status=ContentStatus.ARCHIVED)
        assert valid.status == ContentStatus.ARCHIVED

    def test_audience_groups_containment(self):
        """Array containment tests for ck_guide_audience_groups."""
        # Positive controls
        g1 = EducationalGuideFactory(audience_groups=[AudienceGroup.GENERAL.value])
        assert g1.audience_groups == [AudienceGroup.GENERAL.value]

        g2 = EducationalGuideFactory(
            audience_groups=[AudienceGroup.GENERAL.value, AudienceGroup.ELDERLY.value]
        )
        assert g2.audience_groups == [AudienceGroup.GENERAL.value, AudienceGroup.ELDERLY.value]

        g3 = EducationalGuideFactory(audience_groups=[])
        assert g3.audience_groups == []

        # Failing case 1: invalid element
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(audience_groups=["KIDS"])
        assert "ck_guide_audience_groups" in str(excinfo.value)

        # Failing case 2: NULL element
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(audience_groups=["GENERAL", None])
        assert "ck_guide_audience_groups" in str(excinfo.value)

    def test_tactics_containment(self):
        """Array containment tests for ck_guide_tactics."""
        # Positive controls
        g1 = EducationalGuideFactory(tactics=[Tactic.URGENCY.value])
        assert g1.tactics == [Tactic.URGENCY.value]

        g2 = EducationalGuideFactory(
            tactics=[Tactic.URGENCY.value, Tactic.FEAR.value]
        )
        assert g2.tactics == [Tactic.URGENCY.value, Tactic.FEAR.value]

        g3 = EducationalGuideFactory(tactics=[])
        assert g3.tactics == []

        # Failing case 1: invalid element
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(tactics=["GREED_PUMP"])
        assert "ck_guide_tactics" in str(excinfo.value)

        # Failing case 2: NULL element
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(tactics=["URGENCY", None])
        assert "ck_guide_tactics" in str(excinfo.value)

    def test_published_audience_cardinality(self):
        """Failing and passing tests for ck_guide_published_audience."""
        # Failing case: PUBLISHED with empty audience_groups []
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(
                    status=ContentStatus.PUBLISHED,
                    audience_groups=[],
                    published_at=timezone.now(),
                )
        assert "ck_guide_published_audience" in str(excinfo.value)

        # Positive control 1: DRAFT with empty audience_groups [] succeeds
        draft_empty = EducationalGuideFactory(
            status=ContentStatus.DRAFT,
            audience_groups=[],
            published_at=None,
        )
        assert draft_empty.audience_groups == []

        # Positive control 2: PUBLISHED with audience_groups >= 1 succeeds
        published_valid = EducationalGuideFactory(
            status=ContentStatus.PUBLISHED,
            audience_groups=["GENERAL"],
            published_at=timezone.now(),
        )
        assert published_valid.status == ContentStatus.PUBLISHED

    def test_published_timestamp(self):
        """Failing and passing tests for ck_guide_published_timestamp."""
        # Failing case: PUBLISHED with published_at=None
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                EducationalGuideFactory(
                    status=ContentStatus.PUBLISHED,
                    audience_groups=["GENERAL"],
                    published_at=None,
                )
        assert "ck_guide_published_timestamp" in str(excinfo.value)

        # Positive control 1: PUBLISHED with published_at succeeds
        published = EducationalGuideFactory(
            status=ContentStatus.PUBLISHED,
            audience_groups=["GENERAL"],
            published_at=timezone.now(),
        )
        assert published.published_at is not None

        # Positive control 2: DRAFT with published_at set succeeds (e.g. unpublishing keeps date)
        draft_with_date = EducationalGuideFactory(
            status=ContentStatus.DRAFT,
            audience_groups=["GENERAL"],
            published_at=timezone.now(),
        )
        assert draft_with_date.published_at is not None

        # Positive control 3: DRAFT without published_at succeeds
        draft_no_date = EducationalGuideFactory(
            status=ContentStatus.DRAFT,
            audience_groups=["GENERAL"],
            published_at=None,
        )
        assert draft_no_date.published_at is None


@pytest.mark.django_db
class TestGuideAssetConstraints:
    def test_duplicate_s3_key_fails(self):
        """Failing-insert test for unique s3_key."""
        GuideAssetFactory(s3_key="guides/g1/diagram.png")
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                GuideAssetFactory(s3_key="guides/g1/diagram.png")
        assert "s3_key" in str(excinfo.value)

        # Positive control: distinct s3_key succeeds
        asset2 = GuideAssetFactory(s3_key="guides/g1/diagram2.png")
        assert asset2.s3_key == "guides/g1/diagram2.png"

    def test_invalid_asset_type_fails(self):
        """Failing-insert test for ck_asset_type."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                GuideAssetFactory(asset_type="VIDEO")
        assert "ck_asset_type" in str(excinfo.value)

        # Positive control: valid asset types succeed
        valid_pdf = GuideAssetFactory(asset_type=AssetType.PDF, alt_text="")
        valid_audio = GuideAssetFactory(asset_type=AssetType.AUDIO, alt_text="")
        valid_img = GuideAssetFactory(asset_type=AssetType.IMAGE, alt_text="Infographic")
        assert valid_pdf.asset_type == AssetType.PDF
        assert valid_audio.asset_type == AssetType.AUDIO
        assert valid_img.asset_type == AssetType.IMAGE

    def test_size_bytes_positive(self):
        """Failing and passing tests for ck_asset_size_bytes_positive."""
        # Failing case 1: 0
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                GuideAssetFactory(size_bytes=0)
        assert "ck_asset_size_bytes_positive" in str(excinfo.value)

        # Failing case 2: -1
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                GuideAssetFactory(size_bytes=-1)
        assert "ck_asset_size_bytes_positive" in str(excinfo.value)

        # Positive control: 1 byte succeeds
        valid = GuideAssetFactory(size_bytes=1)
        assert valid.size_bytes == 1

    def test_duration_positive(self):
        """Failing and passing tests for ck_asset_duration_positive."""
        # Failing case 1: 0
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                GuideAssetFactory(duration_seconds=0)
        assert "ck_asset_duration_positive" in str(excinfo.value)

        # Failing case 2: -1
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                GuideAssetFactory(duration_seconds=-1)
        assert "ck_asset_duration_positive" in str(excinfo.value)

        # Positive control 1: duration 1 second succeeds
        valid_1s = GuideAssetFactory(duration_seconds=1)
        assert valid_1s.duration_seconds == 1

        # Positive control 2: duration None succeeds
        valid_none = GuideAssetFactory(duration_seconds=None)
        assert valid_none.duration_seconds is None

    def test_image_alt_text_rules(self):
        """Failing and passing tests for IMAGE alt_text (ck_asset_image_alt_text & NOT NULL)."""
        # Failing case 1: IMAGE with empty string fails ck_asset_image_alt_text
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                GuideAssetFactory(asset_type=AssetType.IMAGE, alt_text="")
        assert "ck_asset_image_alt_text" in str(excinfo.value)

        # Failing case 2: IMAGE with whitespace-only fails ck_asset_image_alt_text
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                GuideAssetFactory(asset_type=AssetType.IMAGE, alt_text="   ")
        assert "ck_asset_image_alt_text" in str(excinfo.value)

        # Failing case 3: IMAGE with alt_text=None fails NOT NULL constraint (Amendment A)
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                GuideAssetFactory(asset_type=AssetType.IMAGE, alt_text=None)
        err_msg = str(excinfo.value).lower()
        assert "alt_text" in err_msg and "null" in err_msg

        # Positive control 1: IMAGE with non-empty alt_text succeeds
        valid_image = GuideAssetFactory(
            asset_type=AssetType.IMAGE,
            alt_text="Infographic explaining fake delivery SMS",
        )
        assert valid_image.alt_text == "Infographic explaining fake delivery SMS"

        # Positive control 2: PDF with empty alt_text succeeds
        valid_pdf = GuideAssetFactory(asset_type=AssetType.PDF, alt_text="")
        assert valid_pdf.alt_text == ""

        # Positive control 3: AUDIO with empty alt_text succeeds
        valid_audio = GuideAssetFactory(asset_type=AssetType.AUDIO, alt_text="")
        assert valid_audio.alt_text == ""


@pytest.mark.django_db
class TestLiteracyBoundariesAndRelationships:
    def test_educational_guide_field_boundaries(self):
        """Boundary-pass tests for max string lengths."""
        slug_200 = "s" * 200
        title_200 = "t" * 200
        summary_500 = "u" * 500

        guide = EducationalGuideFactory(
            slug=slug_200,
            title=title_200,
            summary=summary_500,
        )
        assert len(guide.slug) == 200
        assert len(guide.title) == 200
        assert len(guide.summary) == 500

    def test_guide_asset_field_boundaries(self):
        """Boundary-pass tests for asset string lengths."""
        s3_key_300 = "guides/g/" + ("k" * 280) + ".png"
        assert len(s3_key_300) <= 300
        content_type_60 = "a" * 60
        alt_text_300 = "m" * 300

        asset = GuideAssetFactory(
            s3_key=s3_key_300,
            content_type=content_type_60,
            alt_text=alt_text_300,
        )
        assert len(asset.s3_key) == len(s3_key_300)
        assert len(asset.content_type) == 60
        assert len(asset.alt_text) == 300

    def test_guide_author_protect(self):
        """on_delete PROTECT on author FK raises ProtectedError."""
        author = UserFactory(role="EDUCATOR")
        guide = EducationalGuideFactory(author=author)
        assert guide.author_id == author.id

        with pytest.raises(ProtectedError):
            author.delete()

    def test_guide_asset_cascade(self):
        """on_delete CASCADE on guide FK deletes associated assets."""
        guide = EducationalGuideFactory()
        asset1 = GuideAssetFactory(guide=guide)
        asset2 = GuideAssetFactory(guide=guide)

        guide_id = guide.id
        asset1_id = asset1.id
        asset2_id = asset2.id

        assert GuideAsset.objects.filter(guide_id=guide_id).count() == 2

        guide.delete()

        assert not EducationalGuide.objects.filter(id=guide_id).exists()
        assert not GuideAsset.objects.filter(id=asset1_id).exists()
        assert not GuideAsset.objects.filter(id=asset2_id).exists()

    def test_privacy_guide_str_does_not_leak_body(self):
        """EducationalGuide.__str__ must not leak guide body text."""
        secret_body = "SUPER_SECRET_INTERNAL_GUIDE_CONTENT"
        guide = EducationalGuideFactory(
            title="Safe Shopping Online",
            slug="safe-shopping-online",
            body=secret_body,
        )
        str_rep = str(guide)
        assert "Safe Shopping Online" in str_rep
        assert "safe-shopping-online" in str_rep
        assert secret_body not in str_rep

    def test_privacy_asset_str_does_not_leak_alt_text_or_transcript(self):
        """GuideAsset.__str__ must not leak alt_text or transcript."""
        secret_alt = "CONFIDENTIAL_ALT_TEXT_DETAIL"
        secret_transcript = "CONFIDENTIAL_TRANSCRIPT_SPEECH"
        asset = GuideAssetFactory(
            asset_type=AssetType.AUDIO,
            alt_text=secret_alt,
            transcript=secret_transcript,
        )
        str_rep = str(asset)
        assert "AUDIO" in str_rep
        assert str(asset.guide_id) in str_rep
        assert secret_alt not in str_rep
        assert secret_transcript not in str_rep
