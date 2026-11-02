import pytest
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
        email="educator_grading@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def scam_scenario(educator):
    sc = SimulatorScenario.objects.create(
        title="Urgent Scam SMS",
        channel=ScenarioChannel.SMS,
        is_scam=True,
        tactic=ScenarioTactic.URGENCY,
        difficulty=1,
        image_s3_key="scenarios/scam.png",
        image_alt="SMS prompt",
        explanation="Phishing SMS with shortener link.",
        status=ScenarioStatus.PUBLISHED,
        author=educator,
    )
    ScenarioRedFlag.objects.create(
        scenario=sc,
        flag_code=RedFlagCode.SUSPICIOUS_LINK.value,
        x_pct=10.0,
        y_pct=10.0,
        w_pct=20.0,
        h_pct=10.0,
        explanation="Shortened URL hiding real domain.",
    )
    return sc


@pytest.fixture
def legit_scenario(educator):
    return SimulatorScenario.objects.create(
        title="Legit Bank Statement",
        channel=ScenarioChannel.EMAIL,
        is_scam=False,
        tactic=ScenarioTactic.NONE,
        difficulty=1,
        image_s3_key="scenarios/legit.png",
        image_alt="Bank email",
        explanation="No links or sensitive data requested.",
        status=ScenarioStatus.PUBLISHED,
        author=educator,
    )


@pytest.fixture
def attempt(educator, scam_scenario, legit_scenario):
    dummy_scenarios = [
        SimulatorScenario.objects.create(
            title=f"Dummy {i}",
            channel=ScenarioChannel.EMAIL,
            is_scam=False,
            tactic=ScenarioTactic.NONE,
            difficulty=1,
            image_s3_key=f"scenarios/dummy_{i}.png",
            image_alt="Alt",
            explanation="Exp",
            status=ScenarioStatus.PUBLISHED,
            author=educator,
        )
        for i in range(3)
    ]
    scenario_ids = [scam_scenario.id, legit_scenario.id] + [s.id for s in dummy_scenarios]
    return SimulatorAttempt.objects.create(
        scenario_ids=scenario_ids,
        status=AttemptStatus.IN_PROGRESS,
        session_key="11111111-1111-1111-1111-111111111111",
    )


@pytest.mark.django_db
class TestSimulatorGradingAPI:
    def test_scam_with_correct_flag_is_correct(self, attempt, scam_scenario):
        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        payload = {
            "scenario_id": str(scam_scenario.id),
            "answered_is_scam": True,
            "selected_flag_code": RedFlagCode.SUSPICIOUS_LINK.value,
        }
        res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/answers/", data=payload, format="json")
        assert res.status_code == 201
        data = res.json()
        assert data["is_correct"] is True
        assert data["explanation"] == scam_scenario.explanation
        assert len(data["red_flags"]) == 1

        answer = AttemptAnswer.objects.get(attempt=attempt, scenario=scam_scenario)
        assert answer.is_correct is True

    def test_scam_with_wrong_flag_is_incorrect(self, attempt, scam_scenario):
        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        payload = {
            "scenario_id": str(scam_scenario.id),
            "answered_is_scam": True,
            "selected_flag_code": RedFlagCode.TOO_GOOD_TO_BE_TRUE.value,
        }
        res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/answers/", data=payload, format="json")
        assert res.status_code == 201
        data = res.json()
        assert data["is_correct"] is False

        answer = AttemptAnswer.objects.get(attempt=attempt, scenario=scam_scenario)
        assert answer.is_correct is False

    def test_scam_answered_as_legit_is_incorrect(self, attempt, scam_scenario):
        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        payload = {
            "scenario_id": str(scam_scenario.id),
            "answered_is_scam": False,
        }
        res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/answers/", data=payload, format="json")
        assert res.status_code == 201
        data = res.json()
        assert data["is_correct"] is False

    def test_legit_answered_as_legit_is_correct(self, attempt, legit_scenario):
        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        payload = {
            "scenario_id": str(legit_scenario.id),
            "answered_is_scam": False,
        }
        res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/answers/", data=payload, format="json")
        assert res.status_code == 201
        data = res.json()
        assert data["is_correct"] is True

    def test_legit_answered_as_scam_is_incorrect(self, attempt, legit_scenario):
        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        payload = {
            "scenario_id": str(legit_scenario.id),
            "answered_is_scam": True,
            "selected_flag_code": RedFlagCode.POOR_GRAMMAR.value,
        }
        res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/answers/", data=payload, format="json")
        assert res.status_code == 201
        data = res.json()
        assert data["is_correct"] is False

    def test_scenario_not_in_attempt_rejected(self, attempt, educator):
        alien_scenario = SimulatorScenario.objects.create(
            title="Alien Scenario",
            channel=ScenarioChannel.EMAIL,
            is_scam=False,
            tactic=ScenarioTactic.NONE,
            difficulty=1,
            image_s3_key="scenarios/alien.png",
            image_alt="Alt",
            explanation="Exp",
            status=ScenarioStatus.PUBLISHED,
            author=educator,
        )
        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        payload = {
            "scenario_id": str(alien_scenario.id),
            "answered_is_scam": False,
        }
        res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/answers/", data=payload, format="json")
        assert res.status_code == 400

    def test_duplicate_answer_raises_409(self, attempt, legit_scenario):
        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        payload = {
            "scenario_id": str(legit_scenario.id),
            "answered_is_scam": False,
        }
        res1 = client.post(f"/api/v1/simulator/attempts/{attempt.id}/answers/", data=payload, format="json")
        assert res1.status_code == 201

        res2 = client.post(f"/api/v1/simulator/attempts/{attempt.id}/answers/", data=payload, format="json")
        assert res2.status_code == 409
        assert res2.json().get("error", {}).get("code") in ("already_answered", "conflict")
