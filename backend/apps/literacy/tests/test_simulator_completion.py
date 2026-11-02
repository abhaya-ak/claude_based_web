import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.enums import AudienceGroup
from apps.literacy.models import (
    AttemptAnswer,
    AttemptStatus,
    ContentStatus,
    EducationalGuide,
    RedFlagCode,
    ScenarioChannel,
    ScenarioRedFlag,
    ScenarioStatus,
    ScenarioTactic,
    SimulatorAttempt,
    SimulatorScenario,
    Tactic,
)


@pytest.fixture
def educator(db):
    return User.objects.create_user(
        email="educator_comp@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def remediation_guide(educator):
    return EducationalGuide.objects.create(
        slug="urgency-scams-remediation",
        title="Defeating Urgency Tactics",
        summary="How to spot and resist artificial countdowns and urgency.",
        body="Detailed guide on urgency...",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.URGENCY.value],
        language="en",
        status=ContentStatus.PUBLISHED.value,
        published_at="2026-01-01T00:00:00Z",
        author=educator,
    )


@pytest.fixture
def five_scenarios(educator):
    # Scenario 0: URGENCY scam
    # Scenario 1: URGENCY scam
    # Scenario 2: FEAR scam
    # Scenario 3: Legit NONE
    # Scenario 4: Legit NONE
    s0 = SimulatorScenario.objects.create(
        title="Urgency 1",
        channel=ScenarioChannel.SMS,
        is_scam=True,
        tactic=ScenarioTactic.URGENCY,
        difficulty=1,
        image_s3_key="scenarios/u1.png",
        image_alt="Alt",
        explanation="Urgency 1",
        status=ScenarioStatus.PUBLISHED,
        author=educator,
    )
    ScenarioRedFlag.objects.create(
        scenario=s0,
        flag_code=RedFlagCode.ARTIFICIAL_URGENCY,
        x_pct=5.0,
        y_pct=5.0,
        w_pct=10.0,
        h_pct=10.0,
        explanation="Exp",
    )

    s1 = SimulatorScenario.objects.create(
        title="Urgency 2",
        channel=ScenarioChannel.EMAIL,
        is_scam=True,
        tactic=ScenarioTactic.URGENCY,
        difficulty=1,
        image_s3_key="scenarios/u2.png",
        image_alt="Alt",
        explanation="Urgency 2",
        status=ScenarioStatus.PUBLISHED,
        author=educator,
    )
    ScenarioRedFlag.objects.create(
        scenario=s1,
        flag_code=RedFlagCode.ARTIFICIAL_URGENCY,
        x_pct=5.0,
        y_pct=5.0,
        w_pct=10.0,
        h_pct=10.0,
        explanation="Exp",
    )

    s2 = SimulatorScenario.objects.create(
        title="Fear 1",
        channel=ScenarioChannel.WHATSAPP,
        is_scam=True,
        tactic=ScenarioTactic.FEAR,
        difficulty=1,
        image_s3_key="scenarios/f1.png",
        image_alt="Alt",
        explanation="Fear 1",
        status=ScenarioStatus.PUBLISHED,
        author=educator,
    )
    ScenarioRedFlag.objects.create(
        scenario=s2,
        flag_code=RedFlagCode.THREAT_OF_LOSS,
        x_pct=5.0,
        y_pct=5.0,
        w_pct=10.0,
        h_pct=10.0,
        explanation="Exp",
    )

    s3 = SimulatorScenario.objects.create(
        title="Legit 1",
        channel=ScenarioChannel.EMAIL,
        is_scam=False,
        tactic=ScenarioTactic.NONE,
        difficulty=1,
        image_s3_key="scenarios/l1.png",
        image_alt="Alt",
        explanation="Legit 1",
        status=ScenarioStatus.PUBLISHED,
        author=educator,
    )

    s4 = SimulatorScenario.objects.create(
        title="Legit 2",
        channel=ScenarioChannel.WEBSITE,
        is_scam=False,
        tactic=ScenarioTactic.NONE,
        difficulty=1,
        image_s3_key="scenarios/l2.png",
        image_alt="Alt",
        explanation="Legit 2",
        status=ScenarioStatus.PUBLISHED,
        author=educator,
    )

    return [s0, s1, s2, s3, s4]


@pytest.mark.django_db
class TestSimulatorCompletionAPI:
    """
    TO BE PROVEN #21: Simulator completion, blind-spot detection & remediation linkage.
    Asserts >= 2 misses triggers a blind spot; 1 miss does not.
    """

    def test_incomplete_attempt_rejected(self, educator, five_scenarios):
        attempt = SimulatorAttempt.objects.create(
            scenario_ids=[s.id for s in five_scenarios],
            status=AttemptStatus.IN_PROGRESS,
            session_key="22222222-2222-2222-2222-222222222222",
        )
        # Only answer 2 scenarios
        AttemptAnswer.objects.create(attempt=attempt, scenario=five_scenarios[0], answered_is_scam=True, is_correct=True)
        AttemptAnswer.objects.create(attempt=attempt, scenario=five_scenarios[1], answered_is_scam=True, is_correct=True)

        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/complete/")
        assert res.status_code == 400
        assert "incomplete" in str(res.json())

    def test_to_be_proven_21_blind_spot_math_and_remediation_linkage(
        self, educator, five_scenarios, remediation_guide
    ):
        attempt = SimulatorAttempt.objects.create(
            scenario_ids=[s.id for s in five_scenarios],
            status=AttemptStatus.IN_PROGRESS,
            session_key="33333333-3333-3333-3333-333333333333",
        )

        # Answers breakdown:
        # Scenario 0 (URGENCY): missed (is_correct=False) -> miss 1
        # Scenario 1 (URGENCY): missed (is_correct=False) -> miss 2 (triggers blind spot!)
        # Scenario 2 (FEAR): missed (is_correct=False) -> miss 1 (only 1 miss -> NOT a blind spot!)
        # Scenario 3 (Legit): correct (is_correct=True)
        # Scenario 4 (Legit): correct (is_correct=True)
        AttemptAnswer.objects.create(attempt=attempt, scenario=five_scenarios[0], answered_is_scam=False, is_correct=False)
        AttemptAnswer.objects.create(attempt=attempt, scenario=five_scenarios[1], answered_is_scam=False, is_correct=False)
        AttemptAnswer.objects.create(attempt=attempt, scenario=five_scenarios[2], answered_is_scam=False, is_correct=False)
        AttemptAnswer.objects.create(attempt=attempt, scenario=five_scenarios[3], answered_is_scam=False, is_correct=True)
        AttemptAnswer.objects.create(attempt=attempt, scenario=five_scenarios[4], answered_is_scam=False, is_correct=True)

        client = APIClient()
        client.credentials(HTTP_X_SESSION_KEY=str(attempt.session_key))

        res = client.post(f"/api/v1/simulator/attempts/{attempt.id}/complete/")
        assert res.status_code == 200
        data = res.json()

        # Score: 2 correct out of 5 = 40%
        assert data["score_pct"] == 40
        assert data["status"] == "COMPLETED"
        assert data["completed_at"] is not None

        # Blind spots verification:
        # URGENCY has 2 misses -> MUST BE a blind spot
        # FEAR has 1 miss -> MUST NOT BE a blind spot
        profile = data["profile"]
        assert "URGENCY" in profile["blind_spots"]
        assert "FEAR" not in profile["blind_spots"]
        assert profile["tactics"]["URGENCY"]["is_blind_spot"] is True
        assert profile["tactics"]["FEAR"]["is_blind_spot"] is False

        # Remediation guides attached for URGENCY
        assert "remediation_guides" in data
        guides = data["remediation_guides"]
        assert len(guides) >= 1
        assert any(g["slug"] == remediation_guide.slug for g in guides)

        # Attempt is now immutable: cannot answer or complete again
        res_answer = client.post(
            f"/api/v1/simulator/attempts/{attempt.id}/answers/",
            data={"scenario_id": str(five_scenarios[0].id), "answered_is_scam": True},
            format="json",
        )
        assert res_answer.status_code == 409

        res_complete_again = client.post(f"/api/v1/simulator/attempts/{attempt.id}/complete/")
        assert res_complete_again.status_code == 409
