import uuid

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.literacy.serializers_simulator import (
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


class SimulatorAttemptInitView(APIView):
    """
    Public endpoint to initialize a 5-scenario simulation attempt.
    Supports authenticated citizens and anonymous players (via X-Session-Key).
    Returns masked scenario cards omitting answers (anti-cheat).
    """

    permission_classes = [AllowAny]

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
