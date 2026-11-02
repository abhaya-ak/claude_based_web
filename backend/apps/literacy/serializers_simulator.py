from rest_framework import serializers

from apps.literacy.models import SimulatorScenario


class SimulatorScenarioCardSerializer(serializers.ModelSerializer):
    """
    Anti-cheat masked scenario card.
    Strictly omits is_scam, tactic, explanation, and red_flags.
    """

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = SimulatorScenario
        fields = [
            "id",
            "title",
            "channel",
            "difficulty",
            "image_url",
            "image_alt",
        ]
        read_only_fields = fields

    def get_image_url(self, obj) -> str:
        if not obj.image_s3_key:
            return ""
        return f"/media/{obj.image_s3_key}"


class SimulatorAttemptInitResponseSerializer(serializers.Serializer):
    """Response payload for simulator attempt initialization."""

    attempt_id = serializers.UUIDField()
    session_key = serializers.UUIDField(allow_null=True)
    scenario_count = serializers.IntegerField(default=5)
    scenarios = SimulatorScenarioCardSerializer(many=True)
