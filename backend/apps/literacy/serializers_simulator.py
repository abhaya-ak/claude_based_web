from rest_framework import serializers

from apps.literacy.models import RedFlagCode, SimulatorAttempt, SimulatorScenario
from apps.literacy.serializers import EducationalGuidePublicListSerializer
from apps.literacy.serializers_scenario import ScenarioRedFlagSerializer


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


class SimulatorAnswerSubmissionSerializer(serializers.Serializer):
    """Payload for submitting an answer to a scenario in an attempt."""

    scenario_id = serializers.UUIDField()
    answered_is_scam = serializers.BooleanField()
    selected_flag_code = serializers.ChoiceField(
        choices=RedFlagCode.choices,
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        answered_is_scam = attrs.get("answered_is_scam")
        selected_flag_code = attrs.get("selected_flag_code")
        if not answered_is_scam and selected_flag_code:
            attrs["selected_flag_code"] = None
        return attrs


class SimulatorAnswerFeedbackSerializer(serializers.Serializer):
    """Immediate feedback after answering a single scenario."""

    scenario_id = serializers.UUIDField()
    is_correct = serializers.BooleanField()
    explanation = serializers.CharField()
    red_flags = ScenarioRedFlagSerializer(many=True)


class SimulatorAttemptCompletionResponseSerializer(serializers.Serializer):
    """Response payload for completed simulator attempt."""

    attempt_id = serializers.UUIDField()
    status = serializers.CharField()
    score_pct = serializers.IntegerField()
    completed_at = serializers.DateTimeField()
    profile = serializers.JSONField()
    remediation_guides = EducationalGuidePublicListSerializer(many=True)


class SimulatorAttemptDetailSerializer(serializers.ModelSerializer):
    """Detail view for a simulator attempt."""

    remediation_guides = serializers.SerializerMethodField()

    class Meta:
        model = SimulatorAttempt
        fields = [
            "id",
            "status",
            "score_pct",
            "profile",
            "started_at",
            "completed_at",
            "remediation_guides",
        ]
        read_only_fields = fields

    def get_remediation_guides(self, obj):
        if obj.status != "COMPLETED" or not obj.profile:
            return []
        blind_spots = obj.profile.get("blind_spots", [])
        if not blind_spots:
            return []
        from apps.literacy.selectors.guide_selectors import guides_for_tactics

        request = self.context.get("request")
        lang = getattr(request, "LANGUAGE_CODE", "en") if request else "en"
        guides = guides_for_tactics(tactics=blind_spots, language=lang)
        return EducationalGuidePublicListSerializer(guides, many=True, context=self.context).data
