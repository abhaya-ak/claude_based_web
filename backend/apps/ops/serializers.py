from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.ops.models import SystemAuditLog


class SystemAuditLogSerializer(serializers.ModelSerializer):
    actor_id = serializers.UUIDField(allow_null=True, read_only=True)
    actor_role = serializers.SerializerMethodField()

    class Meta:
        model = SystemAuditLog
        fields = [
            "id",
            "occurred_at",
            "event_type",
            "severity",
            "actor_id",
            "actor_role",
            "actor_ip_hash",
            "target_type",
            "target_id",
            "metadata",
            "request_id",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_actor_role(self, obj) -> str | None:
        if obj.actor_id and obj.actor:
            return getattr(obj.actor, "role", None)
        return None


class TelemetryQuerySerializer(serializers.Serializer):
    range = serializers.ChoiceField(
        choices=["1h", "6h", "24h", "7d"],
        default="24h",
        required=False,
    )


class TelemetrySeriesItemSerializer(serializers.Serializer):
    timestamp = serializers.CharField()
    value = serializers.FloatField()


class TelemetryResponseSerializer(serializers.Serializer):
    time_range = serializers.CharField()
    period = serializers.IntegerField()
    generated_at = serializers.CharField()
    degraded = serializers.BooleanField()
    infrastructure = serializers.DictField()
    operations = serializers.DictField()
