from rest_framework import serializers

from apps.alerts.models import Channel
from apps.core.enums import AudienceGroup
from apps.reports.models import ScamCategory


class SubscriptionCreateRequestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=Channel.choices)
    endpoint = serializers.CharField(max_length=254, required=True, allow_blank=False)
    audience = serializers.ChoiceField(choices=AudienceGroup.choices)
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=ScamCategory.choices),
        required=False,
        default=list,
    )


class SubscriptionResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    channel = serializers.CharField()
    audience = serializers.CharField()
    categories = serializers.ListField(child=serializers.CharField())
    status = serializers.CharField()
    message = serializers.CharField()
    token = serializers.CharField(required=False, allow_null=True)


class SubscriptionTokenRequestSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=256, required=True, allow_blank=False)


class SubscriptionActionResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
