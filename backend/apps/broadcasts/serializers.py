from rest_framework import serializers


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
