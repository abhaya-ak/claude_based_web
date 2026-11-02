import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.literacy.models import (
    AttemptAnswer,
    AttemptStatus,
    RedFlagCode,
    ScenarioChannel,
    ScenarioRedFlag,
    ScenarioStatus,
    ScenarioTactic,
    SimulatorAttempt,
    SimulatorScenario,
)


@pytest.fixture
def educator(db):
    return User.objects.create_user(
        email="educator_qbounds@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def seeded_scenarios(educator):
    scenarios = []
    for i in range(1, 6):
        is_scam = (i <= 3)
        tactic = ScenarioTactic.URGENCY.value if is_scam else ScenarioTactic.NONE.value
        sc = SimulatorScenario.objects.create(
            title=f"Query Bound Scenario {i}",
            channel=ScenarioChannel.SMS if is_scam else ScenarioChannel.EMAIL,
            is_scam=is_scam,
            tactic=tactic,
            difficulty=1,
            image_s3_key=f"scenarios/qb_{i}.png",
            image_alt=f"Alt {i}",
            explanation=f"Exp {i}",
            status=ScenarioStatus.PUBLISHED,
            author=educator,
        )
        if is_scam:
            ScenarioRedFlag.objects.create(
                scenario=sc,
                flag_code=RedFlagCode.SUSPICIOUS_LINK.value,
                x_pct=10.0,
                y_pct=10.0,
                w_pct=20.0,
                h_pct=10.0,
                explanation=f"Flag {i}",
            )
        scenarios.append(sc)
    return scenarios


@pytest.mark.django_db
class TestSimulatorQueryBounds:
    def test_attempt_init_query_bound(self, seeded_scenarios):
        client = APIClient()
        with CaptureQueriesContext(connection) as ctx:
            res = client.post("/api/v1/simulator/attempts/", {}, format="json")

        assert res.status_code == 201
        # Expected:
        # 1 query for published scenario IDs
        # 1 query to insert SimulatorAttempt
        # 1 query to select the 5 scenarios for serialization
        assert len(ctx) <= 3, f"Expected <= 3 queries on attempt init, got {len(ctx)}: {[q['sql'] for q in ctx]}"

    def test_answer_submission_query_bound(self, educator, seeded_scenarios):
        attempt = SimulatorAttempt.objects.create(
            scenario_ids=[s.id for s in seeded_scenarios],
            status=AttemptStatus.IN_PROGRESS,
            session_key="44444444-4444-4444-4444-444444444444",
        )

        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        scenario = seeded_scenarios[0]
        payload = {
            "scenario_id": str(scenario.id),
            "answered_is_scam": True,
            "selected_flag_code": RedFlagCode.SUSPICIOUS_LINK.value,
        }

        with CaptureQueriesContext(connection) as ctx:
            res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/answers/", payload, format="json")

        assert res.status_code == 201
        assert len(ctx) <= 3, f"Expected <= 3 queries on answer, got {len(ctx)}: {[q['sql'] for q in ctx]}"

    def test_completion_query_bound(self, educator, seeded_scenarios):
        attempt = SimulatorAttempt.objects.create(
            scenario_ids=[s.id for s in seeded_scenarios],
            status=AttemptStatus.IN_PROGRESS,
            session_key="55555555-5555-5555-5555-555555555555",
        )
        for s in seeded_scenarios:
            AttemptAnswer.objects.create(
                attempt=attempt,
                scenario=s,
                answered_is_scam=s.is_scam,
                selected_flag_code=RedFlagCode.SUSPICIOUS_LINK.value if s.is_scam else None,
                is_correct=True,
            )

        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        with CaptureQueriesContext(connection) as ctx:
            res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/complete/")

        assert res.status_code == 200
        # No N+1: query count stays strictly bounded regardless of scenario count
        assert len(ctx) <= 3, f"Expected <= 3 queries on complete, got {len(ctx)}: {[q['sql'] for q in ctx]}"
