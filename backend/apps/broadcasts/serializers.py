from rest_framework import serializers

from apps.broadcasts.models import AdvisorySeverity, ThreatAdvisory
from apps.core.enums import AudienceGroup
from apps.reports.models import ScamCategory


class DailyVolumeSerializer(serializers.Serializer):
    date = serializers.CharField()
    count = serializers.IntegerField()


class PlatformVolumeSerializer(serializers.Serializer):
    platform = serializers.CharField()
    count = serializers.IntegerField()


class CategoryVolumeSerializer(serializers.Serializer):
    category = serializers.CharField()
    count = serializers.IntegerField()


class SeriesVolumeSerializer(serializers.Serializer):
    date = serializers.CharField()
    platform = serializers.CharField()
    category = serializers.CharField()
    count = serializers.IntegerField()


class VolumeAnalyticsResponseSerializer(serializers.Serializer):
    total_reports = serializers.IntegerField()
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    by_day = DailyVolumeSerializer(many=True)
    by_platform = PlatformVolumeSerializer(many=True)
    by_category = CategoryVolumeSerializer(many=True)
    series = SeriesVolumeSerializer(many=True)


class CountryLossesSerializer(serializers.Serializer):
    country = serializers.CharField()
    currency = serializers.CharField()
    total_loss = serializers.CharField()
    report_count = serializers.IntegerField()


class AreaLossesSerializer(serializers.Serializer):
    country = serializers.CharField()
    admin_area = serializers.CharField(allow_null=True)
    currency = serializers.CharField()
    total_loss = serializers.CharField()
    report_count = serializers.IntegerField()


class LossesAnalyticsResponseSerializer(serializers.Serializer):
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    by_country = CountryLossesSerializer(many=True)
    by_area = AreaLossesSerializer(many=True)
    breakdown = AreaLossesSerializer(many=True)


class TacticCountSerializer(serializers.Serializer):
    tactic = serializers.CharField()
    count = serializers.IntegerField()


class SpikeDetailSerializer(serializers.Serializer):
    platform = serializers.CharField()
    category = serializers.CharField()
    last_24h_count = serializers.IntegerField()
    trailing_7d_daily_avg = serializers.FloatField()
    growth_pct = serializers.FloatField(allow_null=True)
    is_spike = serializers.BooleanField()


class ThreatAdvisoryPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThreatAdvisory
        fields = [
            "id",
            "title",
            "body",
            "sms_text",
            "severity",
            "target_audience",
            "category",
            "published_at",
            "created_at",
        ]
        read_only_fields = fields


class ThreatAdvisoryStaffSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    published_by_email = serializers.EmailField(source="published_by.email", read_only=True, allow_null=True)

    class Meta:
        model = ThreatAdvisory
        fields = [
            "id",
            "title",
            "body",
            "sms_text",
            "severity",
            "target_audience",
            "category",
            "related_indicator",
            "status",
            "sns_message_id",
            "created_by",
            "created_by_email",
            "published_by",
            "published_by_email",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "sns_message_id",
            "created_by",
            "created_by_email",
            "published_by",
            "published_by_email",
            "published_at",
            "created_at",
            "updated_at",
        ]


class ThreatAdvisoryCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=True, allow_blank=False)
    body = serializers.CharField(max_length=1500, required=True, allow_blank=False)
    sms_text = serializers.CharField(max_length=140, required=False, allow_null=True, allow_blank=True)
    severity = serializers.ChoiceField(choices=AdvisorySeverity.choices, required=True)
    target_audience = serializers.CharField(max_length=15, required=True)
    category = serializers.ChoiceField(choices=ScamCategory.choices, required=False, allow_null=True)
    related_indicator_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_target_audience(self, value):
        if value != "ALL" and value not in AudienceGroup.values:
            raise serializers.ValidationError(
                f"target_audience must be 'ALL' or one of {AudienceGroup.values}."
            )
        return value

    def validate_related_indicator_id(self, value):
        if value:
            from apps.intel.models import VerifiedIndicator

            if not VerifiedIndicator.objects.filter(id=value).exists():
                raise serializers.ValidationError("Related verified indicator does not exist.")
        return value


class ThreatAdvisoryUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False, allow_blank=False)
    body = serializers.CharField(max_length=1500, required=False, allow_blank=False)
    sms_text = serializers.CharField(max_length=140, required=False, allow_null=True, allow_blank=True)
    severity = serializers.ChoiceField(choices=AdvisorySeverity.choices, required=False)
    target_audience = serializers.CharField(max_length=15, required=False)
    category = serializers.ChoiceField(choices=ScamCategory.choices, required=False, allow_null=True)
    related_indicator_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_target_audience(self, value):
        if value != "ALL" and value not in AudienceGroup.values:
            raise serializers.ValidationError(
                f"target_audience must be 'ALL' or one of {AudienceGroup.values}."
            )
        return value

    def validate_related_indicator_id(self, value):
        if value:
            from apps.intel.models import VerifiedIndicator

            if not VerifiedIndicator.objects.filter(id=value).exists():
                raise serializers.ValidationError("Related verified indicator does not exist.")
        return value
