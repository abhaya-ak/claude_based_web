import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.core.enums import AudienceGroup
from apps.literacy.models import AssetType, ContentStatus, EducationalGuide, GuideAsset, Tactic
from apps.literacy.serializers import (
    EducationalGuideCreateUpdateSerializer,
    EducationalGuidePublicDetailSerializer,
    EducationalGuidePublicListSerializer,
    GuideAssetSerializer,
)


@pytest.mark.django_db
class TestLiteracySerializers:
    def test_asset_serializer_returns_relative_media_path(self):
        user = UserFactory(role="EDUCATOR")
        guide = EducationalGuide.objects.create(
            slug="test-asset-slug",
            title="Asset Guide",
            summary="Summary",
            body="Safe body",
            audience_groups=[AudienceGroup.GENERAL.value],
            tactics=[Tactic.URGENCY.value],
            author=user,
        )
        asset = GuideAsset.objects.create(
            guide=guide,
            asset_type=AssetType.IMAGE.value,
            s3_key=f"guides/{guide.id}/image-01.png",
            content_type="image/png",
            size_bytes=1024,
            alt_text="Infographic",
            sort_order=1,
        )

        serializer = GuideAssetSerializer(asset)
        assert serializer.data["url"] == f"/media/guides/{guide.id}/image-01.png"
        assert "s3.amazonaws.com" not in serializer.data["url"]

    def test_public_detail_serializer_sanitizes_body(self):
        user = UserFactory(role="EDUCATOR")
        malicious_body = "Legit text <script>alert(1)</script><img src=x onerror=alert(2)>"
        guide = EducationalGuide.objects.create(
            slug="xss-test-guide",
            title="XSS Test Guide",
            summary="Summary",
            body=malicious_body,
            audience_groups=[AudienceGroup.GENERAL.value],
            tactics=[Tactic.URGENCY.value],
            author=user,
            status=ContentStatus.PUBLISHED.value,
            published_at=timezone.now(),
        )

        serializer = EducationalGuidePublicDetailSerializer(guide)
        data = serializer.data
        assert "<script>" not in data["body"]
        assert "onerror" not in data["body"]
        assert "Legit text" in data["body"]

    def test_public_list_serializer_excludes_body(self):
        user = UserFactory(role="EDUCATOR")
        guide = EducationalGuide.objects.create(
            slug="list-test-guide",
            title="List Test Guide",
            summary="Brief summary",
            body="Long body",
            audience_groups=[AudienceGroup.GENERAL.value],
            tactics=[Tactic.URGENCY.value],
            author=user,
            status=ContentStatus.PUBLISHED.value,
            published_at=timezone.now(),
        )

        serializer = EducationalGuidePublicListSerializer(guide)
        assert "body" not in serializer.data
        assert serializer.data["summary"] == "Brief summary"

    def test_create_update_serializer_validates_valid_payload(self):
        payload = {
            "title": "New Education Guide",
            "summary": "Educational summary",
            "body": "# Heading\n\nContent details.",
            "audience_groups": [AudienceGroup.GENERAL.value, AudienceGroup.ELDERLY.value],
            "tactics": [Tactic.URGENCY.value],
            "language": "en",
            "readability_mode": "STANDARD",
        }
        serializer = EducationalGuideCreateUpdateSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors

    def test_create_update_serializer_rejects_invalid_enums(self):
        payload = {
            "title": "Invalid Guide",
            "summary": "Summary",
            "body": "Body",
            "audience_groups": ["INVALID_GROUP"],
            "tactics": ["INVALID_TACTIC"],
        }
        serializer = EducationalGuideCreateUpdateSerializer(data=payload)
        assert not serializer.is_valid()
        assert "audience_groups" in serializer.errors or "tactics" in serializer.errors
