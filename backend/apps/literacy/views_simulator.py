import uuid

from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.literacy.models import AttemptAnswer, SimulatorAttempt
from apps.literacy.serializers import EducationalGuidePublicListSerializer
from apps.literacy.serializers_scenario import ScenarioRedFlagSerializer
from apps.literacy.serializers_simulator import (
    SimulatorAnswerFeedbackSerializer,
    SimulatorAnswerSubmissionSerializer,
    SimulatorAttemptCompletionResponseSerializer,
    SimulatorAttemptDetailSerializer,
    SimulatorAttemptInitResponseSerializer,
    SimulatorScenarioCardSerializer,
)
from apps.literacy.services import simulator_service


def _extract_session_key(request) -> uuid.UUID | None:
    raw_key = (
        (request.data.get("session_key") if isinstance(request.data, dict) else None)
        or (request.headers.get("X-Session-Key") if hasattr(request, "headers") else None)
        or (request.META.get("HTTP_X_SESSION_KEY") if hasattr(request, "META") else None)
    )
    if not raw_key:
        return None
    try:
        return uuid.UUID(str(raw_key).strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _check_attempt_access(attempt: SimulatorAttempt, request) -> None:
    """Verifies that the request has permission to access or mutate the attempt."""
    user = getattr(request, "user", None)
    if user and user.is_authenticated and getattr(user, "role", None) == Role.ADMIN:
        return

    if attempt.user_id:
        if user and user.is_authenticated and user.id == attempt.user_id:
            return
        raise PermissionDenied("You do not have permission to access this simulator attempt.")

    if attempt.session_key:
        session_key = _extract_session_key(request)
        if session_key and session_key == attempt.session_key:
            return
        raise PermissionDenied("Missing or invalid X-Session-Key for this simulator attempt.")


class SimulatorAttemptInitView(APIView):
    """
    Public endpoint to initialize a 5-scenario simulation attempt.
    Supports authenticated citizens and anonymous players (via X-Session-Key).
    Returns masked scenario cards omitting answers (anti-cheat).
    """

    permission_classes = [AllowAny]
    throttle_scope = "simulator"
    serializer_class = SimulatorAttemptInitResponseSerializer

    @extend_schema(
        summary="Start simulator attempt",
        responses={201: SimulatorAttemptInitResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        session_key = _extract_session_key(request)
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None

        attempt, scenarios = simulator_service.start_attempt(user=user, session_key=session_key)

        cards_data = SimulatorScenarioCardSerializer(scenarios, many=True).data
        response_data = {
            "attempt_id": attempt.id,
            "session_key": attempt.session_key,
            "scenario_count": len(scenarios),
            "scenarios": cards_data,
        }

        resp = Response(response_data, status=status.HTTP_201_CREATED)
        if attempt.session_key:
            resp["X-Session-Key"] = str(attempt.session_key)
        return resp


class SimulatorAttemptAnswerView(APIView):
    """Submits and grades an answer for one scenario in the attempt."""

    permission_classes = [AllowAny]
    throttle_scope = "simulator"
    serializer_class = SimulatorAnswerFeedbackSerializer

    @extend_schema(
        summary="Submit answer for scenario",
        request=SimulatorAnswerSubmissionSerializer,
        responses={201: SimulatorAnswerFeedbackSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        serializer = SimulatorAnswerSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scenario_id = serializer.validated_data["scenario_id"]

        has_answered = Exists(
            AttemptAnswer.objects.filter(attempt=OuterRef("pk"), scenario_id=scenario_id)
        )
        attempt = get_object_or_404(
            SimulatorAttempt.objects.annotate(has_answered=has_answered),
            pk=pk,
        )
        _check_attempt_access(attempt, request)

        answer, scenario, flags = simulator_service.submit_answer(
            attempt=attempt,
            scenario_id=scenario_id,
            answered_is_scam=serializer.validated_data["answered_is_scam"],
            selected_flag_code=serializer.validated_data.get("selected_flag_code"),
        )

        red_flags_data = ScenarioRedFlagSerializer(flags, many=True).data
        response_data = {
            "scenario_id": scenario.id,
            "is_correct": answer.is_correct,
            "explanation": scenario.explanation,
            "red_flags": red_flags_data,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)


class SimulatorAttemptCompleteView(APIView):
    """Completes the attempt, calculates score, profile, blind spots, and remediation guides."""

    permission_classes = [AllowAny]
    throttle_scope = "simulator"
    serializer_class = SimulatorAttemptCompletionResponseSerializer

    @extend_schema(
        summary="Complete simulator attempt",
        responses={200: SimulatorAttemptCompletionResponseSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        attempt = get_object_or_404(SimulatorAttempt, pk=pk)
        _check_attempt_access(attempt, request)

        language = request.query_params.get("language") or getattr(request, "LANGUAGE_CODE", "en")
        attempt, guides = simulator_service.complete_attempt(attempt, language=language)

        guides_data = EducationalGuidePublicListSerializer(
            guides,
            many=True,
            context={"request": request},
        ).data

        response_data = {
            "attempt_id": attempt.id,
            "status": attempt.status,
            "score_pct": attempt.score_pct,
            "completed_at": attempt.completed_at,
            "profile": attempt.profile,
            "remediation_guides": guides_data,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class SimulatorAttemptDetailView(generics.RetrieveAPIView):
    """Retrieve attempt detail by ID."""

    permission_classes = [AllowAny]
    throttle_scope = "simulator"
    serializer_class = SimulatorAttemptDetailSerializer

    def get_object(self):
        attempt = get_object_or_404(SimulatorAttempt, pk=self.kwargs["pk"])
        _check_attempt_access(attempt, self.request)
        return attempt
