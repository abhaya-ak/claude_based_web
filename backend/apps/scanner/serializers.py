from rest_framework import serializers

from apps.scanner.models import HeuristicRule, RuleType, ScannerConfig


class HeuristicRuleSerializer(serializers.ModelSerializer):
    rule_type = serializers.ChoiceField(choices=RuleType.choices)
    pattern = serializers.CharField(max_length=100)
    weight = serializers.IntegerField(min_value=1, max_value=50)
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = HeuristicRule
        fields = [
            "id",
            "rule_type",
            "pattern",
            "weight",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]
        validators = []  # Handled in view to return 409 ConflictError

    def validate_pattern(self, value: str) -> str:
        norm = value.strip().lower()
        if not norm:
            raise serializers.ValidationError("Pattern cannot be blank.")
        return norm


class ScannerConfigSerializer(serializers.ModelSerializer):
    keyword_cap_points = serializers.IntegerField(min_value=0, max_value=100, required=False)
    ip_url_points = serializers.IntegerField(min_value=0, max_value=100, required=False)
    prior_pending_points = serializers.IntegerField(min_value=0, max_value=100, required=False)
    high_priority_threshold = serializers.IntegerField(min_value=1, max_value=100, required=False)

    class Meta:
        model = ScannerConfig
        fields = [
            "id",
            "keyword_cap_points",
            "ip_url_points",
            "prior_pending_points",
            "high_priority_threshold",
            "ruleset_version",
            "updated_at",
        ]
        read_only_fields = ["id", "ruleset_version", "updated_at"]


class ScanResultCallbackSerializer(serializers.Serializer):
    report_id = serializers.UUIDField(required=True)
    ruleset_version = serializers.IntegerField(min_value=1, required=True)
    risk_score = serializers.IntegerField(min_value=0, max_value=100, required=True)
    is_high_priority = serializers.BooleanField(required=True)
    breakdown = serializers.ListField(
        child=serializers.DictField(),
        required=True,
    )
    lambda_request_id = serializers.CharField(
        max_length=64,
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
    )
