import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.enums import AudienceGroup
from apps.literacy.models import (
    AssetType,
    ContentStatus,
    EducationalGuide,
    GuideAsset,
    Language,
    Tactic,
)


@pytest.fixture
def educator(db):
    return User.objects.create_user(
        email="educator_public@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def guides_fixture(educator):
    now = timezone.now()
    published_en = EducationalGuide.objects.create(
        slug="phishing-basics-en",
        title="Phishing Basics (EN)",
        summary="Summary EN",
        body="## Spotting Fake Emails\n\nNever click unknown links.",
        audience_groups=[AudienceGroup.GENERAL.value, AudienceGroup.ELDERLY.value],
        tactics=[Tactic.URGENCY.value],
        language=Language.EN.value,
        status=ContentStatus.PUBLISHED.value,
        published_at=now,
        author=educator,
    )
    published_ne = EducationalGuide.objects.create(
        slug="lottery-scams-ne",
        title="Lottery Scams (NE)",
        summary="Summary NE",
        body="## चिट्ठा ठगीबाट बच्ने उपाय\n\nकुनै पनि गोप्य पिन नदिनुहोस्।",
        audience_groups=[AudienceGroup.ELDERLY.value],
        tactics=[Tactic.GREED.value, Tactic.URGENCY.value],
        language=Language.NE.value,
        status=ContentStatus.PUBLISHED.value,
        published_at=now,
        author=educator,
    )
    draft_guide = EducationalGuide.objects.create(
        slug="draft-secret-guide",
        title="Draft Guide",
        summary="Summary Draft",
        body="Secret draft body",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.FEAR.value],
        language=Language.EN.value,
        status=ContentStatus.DRAFT.value,
        author=educator,
    )
    archived_guide = EducationalGuide.objects.create(
        slug="archived-old-guide",
        title="Archived Guide",
        summary="Summary Archived",
        body="Old archived body",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.AUTHORITY.value],
        language=Language.EN.value,
        status=ContentStatus.ARCHIVED.value,
        author=educator,
    )
    # Add an asset to published_en
    GuideAsset.objects.create(
        guide=published_en,
        asset_type=AssetType.IMAGE.value,
        s3_key=f"guides/{published_en.id}/infographic.png",
        content_type="image/png",
        size_bytes=1024,
        alt_text="Infographic explaining email headers",
    )
    return {
        "published_en": published_en,
        "published_ne": published_ne,
        "draft": draft_guide,
        "archived": archived_guide,
    }


@pytest.mark.django_db
class TestPublicLiteracyHubAPI:
    def test_public_hub_lists_only_published_guides(self, guides_fixture):
        client = APIClient()
        res = client.get("/api/v1/guides/")
        assert res.status_code == 200

        results = res.data["results"]
        slugs = [g["slug"] for g in results]
        assert "phishing-basics-en" in slugs
        assert "lottery-scams-ne" in slugs
        assert "draft-secret-guide" not in slugs
        assert "archived-old-guide" not in slugs

        # Standard ui_hints
        assert res.data["ui_hints"] == {
            "base_font_px": 16,
            "high_contrast": False,
            "tts": False,
        }

    def test_public_hub_filters_by_group_language_and_tactic(self, guides_fixture):
        client = APIClient()

        # 1. Filter by language=ne
        res_ne = client.get("/api/v1/guides/?language=ne")
        assert res_ne.status_code == 200
        assert res_ne.data["count"] == 1
        assert res_ne.data["results"][0]["slug"] == "lottery-scams-ne"

        # 2. Filter by group=ELDERLY
        res_elderly = client.get("/api/v1/guides/?group=ELDERLY")
        assert res_elderly.status_code == 200
        assert res_elderly.data["count"] == 2
        assert res_elderly.data["ui_hints"] == {
            "base_font_px": 20,
            "high_contrast": True,
            "tts": True,
        }

        # 3. Filter by tactic=GREED
        res_greed = client.get("/api/v1/guides/?tactic=GREED")
        assert res_greed.status_code == 200
        assert res_greed.data["count"] == 1
        assert res_greed.data["results"][0]["slug"] == "lottery-scams-ne"

    def test_public_detail_by_slug(self, guides_fixture):
        client = APIClient()
        pub_en = guides_fixture["published_en"]

        res = client.get(f"/api/v1/guides/{pub_en.slug}/")
        assert res.status_code == 200
        assert res.data["slug"] == pub_en.slug
        assert res.data["title"] == pub_en.title
        assert "Spotting Fake Emails" in res.data["body"]
        assert len(res.data["assets"]) == 1
        assert res.data["assets"][0]["url"].startswith("/media/guides/")

    def test_public_detail_draft_or_archived_returns_404(self, guides_fixture):
        client = APIClient()
        draft = guides_fixture["draft"]
        archived = guides_fixture["archived"]

        assert client.get(f"/api/v1/guides/{draft.slug}/").status_code == 404
        assert client.get(f"/api/v1/guides/{archived.slug}/").status_code == 404
