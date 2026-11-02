import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.literacy.models import (
    AttemptStatus,
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
        email="educator_sim@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen(db):
    return User.objects.create_user(
        email="citizen_sim@scamshield.test",
        password="ValidPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def create_published_scenarios(educator):
    scenarios = []
    # Create 3 scam published scenarios
    for i in range(1, 4):
        sc = SimulatorScenario.objects.create(
            title=f"Scam Scenario {i}",
            channel=ScenarioChannel.SMS,
            is_scam=True,
            tactic=ScenarioTactic.URGENCY,
            difficulty=1,
            image_s3_key=f"scenarios/scam_{i}.png",
            image_alt=f"Alt scam {i}",
            explanation=f"Explanation scam {i}",
            status=ScenarioStatus.PUBLISHED,
            author=educator,
        )
        ScenarioRedFlag.objects.create(
            scenario=sc,
            flag_code="SUSPICIOUS_LINK",
            x_pct=10.0,
            y_pct=10.0,
            w_pct=20.0,
            h_pct=10.0,
            explanation=f"Flag {i}",
        )
        scenarios.append(sc)

    # Create 3 legitimate published scenarios
    for i in range(4, 7):
        sc = SimulatorScenario.objects.create(
            title=f"Legit Scenario {i}",
            channel=ScenarioChannel.EMAIL,
            is_scam=False,
            tactic=ScenarioTactic.NONE,
            difficulty=2,
            image_s3_key=f"scenarios/legit_{i}.png",
            image_alt=f"Alt legit {i}",
            explanation=f"Explanation legit {i}",
            status=ScenarioStatus.PUBLISHED,
            author=educator,
        )
        scenarios.append(sc)

    return scenarios


@pytest.mark.django_db
class TestSimulatorAttemptAPI:
    def test_anonymous_attempt_init_generates_session_key(self, create_published_scenarios):
        client = APIClient()
        res = client.post("/api/v1/simulator/attempts/", data={}, format="json")
        assert res.status_code == 201
        data = res.json()

        assert "attempt_id" in data
        assert "session_key" in data
        assert data["session_key"] is not None
        assert res.headers.get("X-Session-Key") == str(data["session_key"])
        assert data["scenario_count"] == 5
        assert len(data["scenarios"]) == 5

        # Check DB row
        attempt = SimulatorAttempt.objects.get(id=data["attempt_id"])
        assert attempt.user is None
        assert str(attempt.session_key) == str(data["session_key"])
        assert attempt.status == AttemptStatus.IN_PROGRESS
        assert len(attempt.scenario_ids) == 5
        assert len(set(attempt.scenario_ids)) == 5  # distinct

    def test_authenticated_user_links_user_id(self, citizen, create_published_scenarios):
        client = APIClient()
        client.force_authenticate(user=citizen)

        res = client.post("/api/v1/simulator/attempts/", data={}, format="json")
        assert res.status_code == 201
        data = res.json()

        attempt = SimulatorAttempt.objects.get(id=data["attempt_id"])
        assert attempt.user == citizen

    def test_anonymous_client_provided_session_key_is_preserved(self, create_published_scenarios):
        client = APIClient()
        existing_session = str(uuid.uuid4())
        client.credentials(HTTP_X_SESSION_KEY=existing_session)

        res = client.post("/api/v1/simulator/attempts/", data={}, format="json")
        assert res.status_code == 201
        data = res.json()
        assert str(data["session_key"]) == existing_session
        assert res.headers.get("X-Session-Key") == existing_session

    def test_insufficient_scenarios_returns_409(self, educator):
        # Only 2 published scenarios in DB
        SimulatorScenario.objects.create(
            title="Scam 1",
            channel=ScenarioChannel.SMS,
            is_scam=False,
            tactic=ScenarioTactic.NONE,
            difficulty=1,
            image_s3_key="scenarios/1.png",
            image_alt="Alt",
            explanation="Exp",
            status=ScenarioStatus.PUBLISHED,
            author=educator,
        )
        SimulatorScenario.objects.create(
            title="Scam 2",
            channel=ScenarioChannel.EMAIL,
            is_scam=False,
            tactic=ScenarioTactic.NONE,
            difficulty=1,
            image_s3_key="scenarios/2.png",
            image_alt="Alt",
            explanation="Exp",
            status=ScenarioStatus.PUBLISHED,
            author=educator,
        )

        client = APIClient()
        res = client.post("/api/v1/simulator/attempts/", data={}, format="json")
        assert res.status_code == 409
        data = res.json()
        assert data.get("error", {}).get("code") in ("insufficient_scenarios", "conflict")

    def test_draft_or_archived_scenarios_are_never_sampled(self, educator, create_published_scenarios):
        draft_scenario = SimulatorScenario.objects.create(
            title="Secret Draft Scenario",
            channel=ScenarioChannel.WEBSITE,
            is_scam=False,
            tactic=ScenarioTactic.NONE,
            difficulty=1,
            image_s3_key="scenarios/draft.png",
            image_alt="Alt",
            explanation="Draft explanation",
            status=ScenarioStatus.DRAFT,
            author=educator,
        )
        archived_scenario = SimulatorScenario.objects.create(
            title="Old Archived Scenario",
            channel=ScenarioChannel.WEBSITE,
            is_scam=False,
            tactic=ScenarioTactic.NONE,
            difficulty=1,
            image_s3_key="scenarios/archived.png",
            image_alt="Alt",
            explanation="Archived explanation",
            status=ScenarioStatus.ARCHIVED,
            author=educator,
        )

        client = APIClient()
        for _ in range(5):
            res = client.post("/api/v1/simulator/attempts/", data={}, format="json")
            assert res.status_code == 201
            sampled_ids = [s["id"] for s in res.json()["scenarios"]]
            assert str(draft_scenario.id) not in sampled_ids
            assert str(archived_scenario.id) not in sampled_ids
