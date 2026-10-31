import uuid
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
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
from apps.literacy.tests.factories import (
    AttemptAnswerFactory,
    EducationalGuideFactory,
    GuideAssetFactory,
    ScenarioRedFlagFactory,
    SimulatorAttemptFactory,
    SimulatorScenarioFactory,
)


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


@pytest.mark.django_db
class TestSimulatorEnums:
    def test_scenario_tactic_matches_tactic_plus_none(self):
        """Amendment C: ScenarioTactic.values must equal Tactic.values plus NONE."""
        expected = [*Tactic.values, "NONE"]
        assert ScenarioTactic.values == expected


@pytest.mark.django_db
class TestSimulatorScenarioConstraints:
    def test_invalid_channel_fails(self):
        """Failing-insert test for ck_scenario_channel."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorScenarioFactory(channel="BROADCAST")
        assert "ck_scenario_channel" in str(excinfo.value)

        # Positive control: valid channel succeeds
        valid = SimulatorScenarioFactory(channel=ScenarioChannel.SMS)
        assert valid.channel == ScenarioChannel.SMS

    def test_invalid_tactic_fails(self):
        """Failing-insert test for ck_scenario_tactic."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorScenarioFactory(tactic="GREED_PUMP")
        assert "ck_scenario_tactic" in str(excinfo.value)

        # Positive control: valid tactic succeeds
        valid = SimulatorScenarioFactory(tactic=ScenarioTactic.URGENCY)
        assert valid.tactic == ScenarioTactic.URGENCY

    def test_invalid_status_fails(self):
        """Amendment A: Failing-insert test for ck_scenario_status with status='REVIEW'."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorScenarioFactory(status="REVIEW")
        assert "ck_scenario_status" in str(excinfo.value)

        # Positive control: valid status succeeds
        valid = SimulatorScenarioFactory(status=ScenarioStatus.PUBLISHED)
        assert valid.status == ScenarioStatus.PUBLISHED

    def test_difficulty_boundaries(self):
        """Failing and passing tests for ck_scenario_difficulty (1..3)."""
        # Failing case 1: 0
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorScenarioFactory(difficulty=0)
        assert "ck_scenario_difficulty" in str(excinfo.value)

        # Failing case 2: 4
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorScenarioFactory(difficulty=4)
        assert "ck_scenario_difficulty" in str(excinfo.value)

        # Positive controls: 1, 2, 3 succeed
        d1 = SimulatorScenarioFactory(difficulty=1)
        d2 = SimulatorScenarioFactory(difficulty=2)
        d3 = SimulatorScenarioFactory(difficulty=3)
        assert d1.difficulty == 1
        assert d2.difficulty == 2
        assert d3.difficulty == 3

    def test_legit_scenario_tactic_rules(self):
        """Failing and passing tests for ck_scenario_legit_tactic_none."""
        # Failing case: is_scam=False with tactic != NONE
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorScenarioFactory(is_scam=False, tactic=ScenarioTactic.URGENCY)
        assert "ck_scenario_legit_tactic_none" in str(excinfo.value)

        # Positive control: is_scam=False with tactic=NONE succeeds
        legit = SimulatorScenarioFactory(is_scam=False, tactic=ScenarioTactic.NONE)
        assert legit.is_scam is False
        assert legit.tactic == ScenarioTactic.NONE

    def test_scam_scenario_has_tactic_rules(self):
        """D16: Failing and passing tests for ck_scenario_scam_has_tactic."""
        # Failing case: is_scam=True with tactic=NONE
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorScenarioFactory(is_scam=True, tactic=ScenarioTactic.NONE)
        assert "ck_scenario_scam_has_tactic" in str(excinfo.value)

        # Positive control: is_scam=True with tactic != NONE succeeds
        scam = SimulatorScenarioFactory(is_scam=True, tactic=ScenarioTactic.FEAR)
        assert scam.is_scam is True
        assert scam.tactic == ScenarioTactic.FEAR


@pytest.mark.django_db
class TestScenarioRedFlagConstraints:
    def test_invalid_flag_code_fails(self):
        """Failing-insert test for ck_flag_code."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(flag_code="SUSPICIOUS")
        assert "ck_flag_code" in str(excinfo.value)

        # Positive control: valid flag_code succeeds
        valid = ScenarioRedFlagFactory(flag_code=RedFlagCode.MISMATCHED_DOMAIN)
        assert valid.flag_code == RedFlagCode.MISMATCHED_DOMAIN

    def test_coordinate_ranges(self):
        """Failing and passing tests for x_pct, y_pct, w_pct, h_pct ranges."""
        # x_pct: -0.01 and 100.01 fail
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(x_pct=Decimal("-0.01"), w_pct=Decimal("10.00"))
        assert "ck_flag_x_pct_range" in str(excinfo.value)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(x_pct=Decimal("100.01"), w_pct=Decimal("0.00"))
        assert ("ck_flag_x_pct_range" in str(excinfo.value) or "ck_flag_w_pct_range" in str(excinfo.value))

        # y_pct: -0.01 fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(y_pct=Decimal("-0.01"))
        assert "ck_flag_y_pct_range" in str(excinfo.value)

        # w_pct: 0.00 and -1.00 fail (D16)
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(w_pct=Decimal("0.00"))
        assert "ck_flag_w_pct_range" in str(excinfo.value)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(w_pct=Decimal("-1.00"))
        assert "ck_flag_w_pct_range" in str(excinfo.value)

        # h_pct: 0.00 and -1.00 fail (D16)
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(h_pct=Decimal("0.00"))
        assert "ck_flag_h_pct_range" in str(excinfo.value)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(h_pct=Decimal("-1.00"))
        assert "ck_flag_h_pct_range" in str(excinfo.value)

        # Positive controls: boundary values 0.00/100.00 for origin, 0.01/100.00 for size
        valid_origin = ScenarioRedFlagFactory(
            x_pct=Decimal("0.00"),
            y_pct=Decimal("0.00"),
            w_pct=Decimal("100.00"),
            h_pct=Decimal("100.00"),
        )
        assert valid_origin.x_pct == Decimal("0.00")
        assert valid_origin.w_pct == Decimal("100.00")

    def test_bounding_box_within_bounds(self):
        """Failing and passing tests for x+w <= 100 and y+h <= 100."""
        # x + w = 60.00 + 40.01 = 100.01 fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(x_pct=Decimal("60.00"), w_pct=Decimal("40.01"))
        assert "ck_flag_x_plus_w_bound" in str(excinfo.value)

        # x + w = 60.00 + 40.00 = 100.00 passes
        valid_x = ScenarioRedFlagFactory(x_pct=Decimal("60.00"), w_pct=Decimal("40.00"))
        assert valid_x.x_pct + valid_x.w_pct == Decimal("100.00")

        # y + h = 70.00 + 30.01 = 100.01 fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScenarioRedFlagFactory(y_pct=Decimal("70.00"), h_pct=Decimal("30.01"))
        assert "ck_flag_y_plus_h_bound" in str(excinfo.value)

        # y + h = 70.00 + 30.00 = 100.00 passes
        valid_y = ScenarioRedFlagFactory(y_pct=Decimal("70.00"), h_pct=Decimal("30.00"))
        assert valid_y.y_pct + valid_y.h_pct == Decimal("100.00")


@pytest.mark.django_db
class TestSimulatorAttemptConstraints:
    def test_invalid_attempt_status_fails(self):
        """Failing-insert test for ck_attempt_status."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorAttemptFactory(status="ABANDONED")
        assert "ck_attempt_status" in str(excinfo.value)

        # Positive control: valid status succeeds
        valid = SimulatorAttemptFactory(status=AttemptStatus.IN_PROGRESS)
        assert valid.status == AttemptStatus.IN_PROGRESS

    def test_user_or_session_key_required(self):
        """Failing and passing tests for ck_attempt_user_or_session."""
        # Failing case: user=None and session_key=None
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorAttemptFactory(user=None, session_key=None)
        assert "ck_attempt_user_or_session" in str(excinfo.value)

        # Positive control 1: user provided
        valid_user = SimulatorAttemptFactory(user=UserFactory(), session_key=None)
        assert valid_user.user is not None

        # Positive control 2: session_key provided
        valid_session = SimulatorAttemptFactory(user=None, session_key=uuid.uuid4())
        assert valid_session.session_key is not None

    def test_score_pct_boundaries(self):
        """Failing and passing tests for ck_attempt_score_pct_range (0..100 or null)."""
        # Failing case 1: -1
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorAttemptFactory(score_pct=-1)
        assert "ck_attempt_score_pct_range" in str(excinfo.value)

        # Failing case 2: 101
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorAttemptFactory(score_pct=101)
        assert "ck_attempt_score_pct_range" in str(excinfo.value)

        # Positive controls: None, 0, 100 succeed
        s_none = SimulatorAttemptFactory(score_pct=None)
        s_0 = SimulatorAttemptFactory(score_pct=0)
        s_100 = SimulatorAttemptFactory(score_pct=100)
        assert s_none.score_pct is None
        assert s_0.score_pct == 0
        assert s_100.score_pct == 100

    def test_completed_attempt_requirements(self):
        """D16: COMPLETED status requires completed_at and score_pct."""
        now = timezone.now()

        # Failing case 1: COMPLETED without completed_at
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorAttemptFactory(
                    status=AttemptStatus.COMPLETED,
                    completed_at=None,
                    score_pct=80,
                )
        assert "ck_attempt_completed_fields" in str(excinfo.value)

        # Failing case 2: COMPLETED without score_pct
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorAttemptFactory(
                    status=AttemptStatus.COMPLETED,
                    completed_at=now,
                    score_pct=None,
                )
        assert "ck_attempt_completed_fields" in str(excinfo.value)

        # Positive control 1: COMPLETED with both succeeds
        valid_completed = SimulatorAttemptFactory(
            status=AttemptStatus.COMPLETED,
            completed_at=now,
            score_pct=80,
        )
        assert valid_completed.status == AttemptStatus.COMPLETED
        assert valid_completed.completed_at is not None
        assert valid_completed.score_pct == 80

        # Positive control 2: IN_PROGRESS without either succeeds
        valid_in_prog = SimulatorAttemptFactory(
            status=AttemptStatus.IN_PROGRESS,
            completed_at=None,
            score_pct=None,
        )
        assert valid_in_prog.status == AttemptStatus.IN_PROGRESS

    def test_scenario_count_constraint(self):
        """D17 & Amendment B1: CARDINALITY(scenario_ids) = 5."""
        # Failing case 1: empty array []
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorAttemptFactory(scenario_ids=[])
        assert "ck_attempt_scenario_count" in str(excinfo.value)

        # Failing case 2: 4 ids
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorAttemptFactory(scenario_ids=[uuid.uuid4() for _ in range(4)])
        assert "ck_attempt_scenario_count" in str(excinfo.value)

        # Failing case 3: 6 ids
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SimulatorAttemptFactory(scenario_ids=[uuid.uuid4() for _ in range(6)])
        assert "ck_attempt_scenario_count" in str(excinfo.value)

        # Positive control: exactly 5 ids succeeds
        valid_5 = SimulatorAttemptFactory(scenario_ids=[uuid.uuid4() for _ in range(5)])
        assert len(valid_5.scenario_ids) == 5


@pytest.mark.django_db
class TestAttemptAnswerConstraints:
    def test_duplicate_attempt_scenario_fails(self):
        """Failing-insert test for uq_answer_attempt_scenario."""
        attempt = SimulatorAttemptFactory()
        scenario = SimulatorScenarioFactory()

        AttemptAnswerFactory(attempt=attempt, scenario=scenario)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AttemptAnswerFactory(attempt=attempt, scenario=scenario)
        assert "uq_answer_attempt_scenario" in str(excinfo.value)

        # Positive control: answering a different scenario in same attempt succeeds
        scenario2 = SimulatorScenarioFactory()
        valid2 = AttemptAnswerFactory(attempt=attempt, scenario=scenario2)
        assert valid2.scenario_id == scenario2.id

    def test_selected_flag_code_validation(self):
        """D16: selected_flag_code is NULL or valid RedFlagCode."""
        # Failing case: invalid flag code
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AttemptAnswerFactory(
                    answered_is_scam=True,
                    selected_flag_code="INVALID_CODE",
                )
        assert "ck_answer_selected_flag_code" in str(excinfo.value)

        # Positive control 1: None succeeds
        valid_none = AttemptAnswerFactory(
            answered_is_scam=True,
            selected_flag_code=None,
        )
        assert valid_none.selected_flag_code is None

        # Positive control 2: valid RedFlagCode succeeds
        valid_code = AttemptAnswerFactory(
            answered_is_scam=True,
            selected_flag_code=RedFlagCode.MISMATCHED_DOMAIN,
        )
        assert valid_code.selected_flag_code == RedFlagCode.MISMATCHED_DOMAIN

    def test_answer_flag_only_if_scam(self):
        """D17 & Amendment B2: answered_is_scam = TRUE OR selected_flag_code IS NULL."""
        # Failing case: answered_is_scam=False with a flag code
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AttemptAnswerFactory(
                    answered_is_scam=False,
                    selected_flag_code=RedFlagCode.POOR_GRAMMAR,
                )
        assert "ck_answer_flag_only_if_scam" in str(excinfo.value)

        # Positive control 1: (False, None) passes
        p1 = AttemptAnswerFactory(answered_is_scam=False, selected_flag_code=None)
        assert p1.answered_is_scam is False
        assert p1.selected_flag_code is None

        # Positive control 2: (True, None) passes
        p2 = AttemptAnswerFactory(answered_is_scam=True, selected_flag_code=None)
        assert p2.answered_is_scam is True
        assert p2.selected_flag_code is None

        # Positive control 3: (True, "POOR_GRAMMAR") passes
        p3 = AttemptAnswerFactory(
            answered_is_scam=True,
            selected_flag_code=RedFlagCode.POOR_GRAMMAR,
        )
        assert p3.answered_is_scam is True
        assert p3.selected_flag_code == RedFlagCode.POOR_GRAMMAR


@pytest.mark.django_db
class TestSimulatorBoundariesAndRelationships:
    def test_scenario_and_flag_boundaries(self):
        """Boundary-pass tests for scenario and red flag string lengths."""
        scenario = SimulatorScenarioFactory(
            title="s" * 150,
            image_s3_key="scenarios/" + ("k" * 280) + ".png",
            image_alt="a" * 300,
        )
        assert len(scenario.title) == 150
        assert len(scenario.image_s3_key) <= 300
        assert len(scenario.image_alt) == 300

        flag = ScenarioRedFlagFactory(
            scenario=scenario,
            explanation="e" * 300,
        )
        assert len(flag.explanation) == 300

    def test_scenario_author_protect(self):
        """on_delete PROTECT on scenario author raises ProtectedError."""
        author = UserFactory(role="EDUCATOR")
        scenario = SimulatorScenarioFactory(author=author)
        assert scenario.author_id == author.id

        with pytest.raises(ProtectedError):
            author.delete()

    def test_scenario_delete_cascades_red_flags(self):
        """on_delete CASCADE from scenario to red flags deletes red flags."""
        scenario = SimulatorScenarioFactory()
        flag1 = ScenarioRedFlagFactory(scenario=scenario)
        flag2 = ScenarioRedFlagFactory(scenario=scenario)

        scenario_id = scenario.id
        flag1_id = flag1.id
        flag2_id = flag2.id

        assert ScenarioRedFlag.objects.filter(scenario_id=scenario_id).count() == 2

        scenario.delete()

        assert not SimulatorScenario.objects.filter(id=scenario_id).exists()
        assert not ScenarioRedFlag.objects.filter(id=flag1_id).exists()
        assert not ScenarioRedFlag.objects.filter(id=flag2_id).exists()

    def test_scenario_referenced_by_answer_protect(self):
        """on_delete PROTECT on AttemptAnswer.scenario raises ProtectedError."""
        scenario = SimulatorScenarioFactory()
        AttemptAnswerFactory(scenario=scenario)

        with pytest.raises(ProtectedError):
            scenario.delete()

    def test_attempt_delete_cascades_answers(self):
        """on_delete CASCADE from attempt to answers deletes answers."""
        attempt = SimulatorAttemptFactory()
        ans1 = AttemptAnswerFactory(attempt=attempt)
        ans2 = AttemptAnswerFactory(attempt=attempt)

        attempt_id = attempt.id
        ans1_id = ans1.id
        ans2_id = ans2.id

        assert AttemptAnswer.objects.filter(attempt_id=attempt_id).count() == 2

        attempt.delete()

        assert not SimulatorAttempt.objects.filter(id=attempt_id).exists()
        assert not AttemptAnswer.objects.filter(id=ans1_id).exists()
        assert not AttemptAnswer.objects.filter(id=ans2_id).exists()

    def test_attempt_user_delete_set_null(self):
        """on_delete SET_NULL on SimulatorAttempt.user nulls user_id."""
        user = UserFactory(role="CITIZEN")
        # Provide session_key so attempt maintains ck_attempt_user_or_session integrity
        session_token = uuid.uuid4()
        attempt = SimulatorAttemptFactory(user=user, session_key=session_token)
        attempt_id = attempt.id

        user.delete()

        attempt.refresh_from_db()
        assert attempt.user_id is None
        assert attempt.session_key == session_token
        assert SimulatorAttempt.objects.filter(id=attempt_id).exists()

    def test_privacy_scenario_str(self):
        """SimulatorScenario.__str__ must not leak explanation or image_alt."""
        secret_exp = "INTERNAL_EXPLANATION_DETAILS"
        secret_alt = "CONFIDENTIAL_ALT_TEXT_DETAILS"
        scenario = SimulatorScenarioFactory(
            title="Fake Tax Refund SMS",
            explanation=secret_exp,
            image_alt=secret_alt,
        )
        str_rep = str(scenario)
        assert "Fake Tax Refund SMS" in str_rep
        assert str(scenario.id) in str_rep
        assert secret_exp not in str_rep
        assert secret_alt not in str_rep

    def test_privacy_red_flag_str(self):
        """ScenarioRedFlag.__str__ must not leak explanation."""
        secret_exp = "INTERNAL_FLAG_EXPLANATION_TEXT"
        flag = ScenarioRedFlagFactory(
            explanation=secret_exp,
        )
        str_rep = str(flag)
        assert str(flag.flag_code) in str_rep
        assert str(flag.scenario_id) in str_rep
        assert secret_exp not in str_rep

    def test_privacy_attempt_str(self):
        """SimulatorAttempt.__str__ must not leak profile or session_key."""
        secret_session = uuid.uuid4()
        attempt = SimulatorAttemptFactory(
            session_key=secret_session,
            profile={"SECRET": {"correct": 1, "total": 2}},
        )
        str_rep = str(attempt)
        assert str(attempt.id) in str_rep
        assert "IN_PROGRESS" in str_rep
        assert str(secret_session) not in str_rep
        assert "SECRET" not in str_rep

    def test_privacy_answer_str(self):
        """AttemptAnswer.__str__ must not leak selected_flag_code or is_correct."""
        answer = AttemptAnswerFactory(
            selected_flag_code=RedFlagCode.MISMATCHED_DOMAIN,
            is_correct=True,
        )
        str_rep = str(answer)
        assert str(answer.id) in str_rep
        assert str(answer.attempt_id) in str_rep
        assert "MISMATCHED_DOMAIN" not in str_rep
        assert "True" not in str_rep

