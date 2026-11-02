from decimal import Decimal

from rest_framework import serializers

from apps.literacy.models import (
    RedFlagCode,
    ScenarioChannel,
    ScenarioRedFlag,
    ScenarioTactic,
    SimulatorScenario,
)


class ScenarioRedFlagSerializer(serializers.ModelSerializer):
    """Serializer for scenario red flag hotspot details."""

    class Meta:
        model = ScenarioRedFlag
        fields = [
            "id",
            "scenario_id",
            "flag_code",
            "x_pct",
            "y_pct",
            "w_pct",
            "h_pct",
            "explanation",
        ]
        read_only_fields = ["id", "scenario_id"]


class ScenarioRedFlagCreateSerializer(serializers.ModelSerializer):
    """Validation serializer for creating a red flag hotspot."""

    flag_code = serializers.ChoiceField(choices=RedFlagCode.choices)
    x_pct = serializers.DecimalField(max_digits=5, decimal_places=2)
    y_pct = serializers.DecimalField(max_digits=5, decimal_places=2)
    w_pct = serializers.DecimalField(max_digits=5, decimal_places=2)
    h_pct = serializers.DecimalField(max_digits=5, decimal_places=2)
    explanation = serializers.CharField(max_length=300)

    class Meta:
        model = ScenarioRedFlag
        fields = ["flag_code", "x_pct", "y_pct", "w_pct", "h_pct", "explanation"]

    def validate(self, attrs):
        x = attrs.get("x_pct")
        y = attrs.get("y_pct")
        w = attrs.get("w_pct")
        h = attrs.get("h_pct")

        errors = {}
        if x is not None:
            if x < Decimal("0.00") or x > Decimal("100.00"):
                errors["x_pct"] = ["x_pct must be between 0 and 100."]
        if y is not None:
            if y < Decimal("0.00") or y > Decimal("100.00"):
                errors["y_pct"] = ["y_pct must be between 0 and 100."]
        if w is not None:
            if w <= Decimal("0.00") or w > Decimal("100.00"):
                errors["w_pct"] = ["w_pct must be greater than 0 and up to 100."]
        if h is not None:
            if h <= Decimal("0.00") or h > Decimal("100.00"):
                errors["h_pct"] = ["h_pct must be greater than 0 and up to 100."]

        if not errors:
            if (x + w) > Decimal("100.00"):
                errors["w_pct"] = ["Hotspot extends beyond image width (x_pct + w_pct > 100)."]
            if (y + h) > Decimal("100.00"):
                errors["h_pct"] = ["Hotspot extends beyond image height (y_pct + h_pct > 100)."]

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class StudioScenarioSerializer(serializers.ModelSerializer):
    """Detailed serializer for educators & admins viewing studio scenarios."""

    author_email = serializers.EmailField(source="author.email", read_only=True)
    image_url = serializers.SerializerMethodField()
    red_flags = ScenarioRedFlagSerializer(many=True, read_only=True)

    class Meta:
        model = SimulatorScenario
        fields = [
            "id",
            "title",
            "channel",
            "is_scam",
            "tactic",
            "difficulty",
            "image_s3_key",
            "image_url",
            "image_alt",
            "explanation",
            "status",
            "author_id",
            "author_email",
            "red_flags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "image_s3_key",
            "image_url",
            "status",
            "author_id",
            "author_email",
            "red_flags",
            "created_at",
            "updated_at",
        ]

    def get_image_url(self, obj) -> str:
        if not obj.image_s3_key:
            return ""
        return f"/media/{obj.image_s3_key}"


class StudioScenarioCreateSerializer(serializers.Serializer):
    """Validation serializer for scenario creation (multipart form)."""

    title = serializers.CharField(max_length=150)
    channel = serializers.ChoiceField(choices=ScenarioChannel.choices)
    is_scam = serializers.BooleanField()
    tactic = serializers.ChoiceField(choices=ScenarioTactic.choices)
    difficulty = serializers.IntegerField(min_value=1, max_value=3)
    image_alt = serializers.CharField(max_length=300)
    explanation = serializers.CharField()
    image = serializers.FileField(required=True)

    def validate(self, attrs):
        is_scam = attrs.get("is_scam")
        tactic = attrs.get("tactic")

        if is_scam is False and tactic != ScenarioTactic.NONE.value:
            raise serializers.ValidationError(
                {"tactic": ["Legitimate scenarios must have tactic 'NONE'."]},
                code="invalid_tactic",
            )
        if is_scam is True and tactic == ScenarioTactic.NONE.value:
            raise serializers.ValidationError(
                {"tactic": ["Scam scenarios must specify a tactic other than 'NONE'."]},
                code="invalid_tactic",
            )
        return attrs


class StudioScenarioUpdateSerializer(serializers.Serializer):
    """Validation serializer for updating scenario fields."""

    title = serializers.CharField(max_length=150, required=False)
    channel = serializers.ChoiceField(choices=ScenarioChannel.choices, required=False)
    is_scam = serializers.BooleanField(required=False)
    tactic = serializers.ChoiceField(choices=ScenarioTactic.choices, required=False)
    difficulty = serializers.IntegerField(min_value=1, max_value=3, required=False)
    image_alt = serializers.CharField(max_length=300, required=False)
    explanation = serializers.CharField(required=False)
    image = serializers.FileField(required=False)

    def validate(self, attrs):
        # We also need to check consistency with instance if partial
        instance = getattr(self, "instance", None)
        is_scam = attrs.get("is_scam", getattr(instance, "is_scam", None))
        tactic = attrs.get("tactic", getattr(instance, "tactic", None))

        if is_scam is not None and tactic is not None:
            if is_scam is False and tactic != ScenarioTactic.NONE.value:
                raise serializers.ValidationError(
                    {"tactic": ["Legitimate scenarios must have tactic 'NONE'."]},
                    code="invalid_tactic",
                )
            if is_scam is True and tactic == ScenarioTactic.NONE.value:
                raise serializers.ValidationError(
                    {"tactic": ["Scam scenarios must specify a tactic other than 'NONE'."]},
                    code="invalid_tactic",
                )
        return attrs
