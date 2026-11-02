from rest_framework import serializers

from apps.core.enums import AudienceGroup
from apps.literacy.models import (
    EducationalGuide,
    GuideAsset,
    Language,
    ReadabilityMode,
    Tactic,
)
from apps.literacy.sanitizers import sanitize_markdown


class GuideAssetSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = GuideAsset
        fields = [
            "id",
            "asset_type",
            "url",
            "content_type",
            "size_bytes",
            "duration_seconds",
            "alt_text",
            "transcript",
            "sort_order",
            "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj: GuideAsset) -> str:
        # Relative CloudFront media path per D115 (never raw S3 URLs)
        return f"/media/{obj.s3_key}"


class EducationalGuidePublicListSerializer(serializers.ModelSerializer):
    assets = GuideAssetSerializer(many=True, read_only=True)

    class Meta:
        model = EducationalGuide
        fields = [
            "id",
            "slug",
            "title",
            "summary",
            "audience_groups",
            "tactics",
            "language",
            "readability_mode",
            "published_at",
            "assets",
        ]
        read_only_fields = fields


class EducationalGuidePublicDetailSerializer(serializers.ModelSerializer):
    body = serializers.SerializerMethodField()
    assets = GuideAssetSerializer(many=True, read_only=True)

    class Meta:
        model = EducationalGuide
        fields = [
            "id",
            "slug",
            "title",
            "summary",
            "body",
            "audience_groups",
            "tactics",
            "language",
            "readability_mode",
            "published_at",
            "assets",
            "created_at",
        ]
        read_only_fields = fields

    def get_body(self, obj: EducationalGuide) -> str:
        return sanitize_markdown(obj.body)


class EducationalGuideStudioSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author.email", read_only=True)
    body = serializers.SerializerMethodField()
    assets = GuideAssetSerializer(many=True, read_only=True)

    class Meta:
        model = EducationalGuide
        fields = [
            "id",
            "slug",
            "title",
            "summary",
            "body",
            "audience_groups",
            "tactics",
            "language",
            "readability_mode",
            "status",
            "author",
            "author_email",
            "published_at",
            "assets",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "status",
            "author",
            "author_email",
            "published_at",
            "assets",
            "created_at",
            "updated_at",
        ]

    def get_body(self, obj: EducationalGuide) -> str:
        return sanitize_markdown(obj.body)


class EducationalGuideCreateUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=True, allow_blank=False)
    summary = serializers.CharField(max_length=500, required=True, allow_blank=False)
    body = serializers.CharField(required=True, allow_blank=False)
    audience_groups = serializers.ListField(
        child=serializers.ChoiceField(choices=AudienceGroup.choices),
        required=False,
        default=list,
    )
    tactics = serializers.ListField(
        child=serializers.ChoiceField(choices=Tactic.choices),
        required=False,
        default=list,
    )
    language = serializers.ChoiceField(
        choices=Language.choices,
        required=False,
        default=Language.EN,
    )
    readability_mode = serializers.ChoiceField(
        choices=ReadabilityMode.choices,
        required=False,
        default=ReadabilityMode.STANDARD,
    )

    def validate_audience_groups(self, value):
        valid = set(AudienceGroup.values)
        for item in value:
            if item not in valid:
                raise serializers.ValidationError(f"Invalid audience group: {item}")
        return list(dict.fromkeys(value))  # deduplicate preserving order

    def validate_tactics(self, value):
        valid = set(Tactic.values)
        for item in value:
            if item not in valid:
                raise serializers.ValidationError(f"Invalid tactic: {item}")
        return list(dict.fromkeys(value))  # deduplicate preserving order
