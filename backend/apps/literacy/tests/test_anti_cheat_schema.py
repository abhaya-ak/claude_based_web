import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.literacy.models import (
    RedFlagCode,
    ScenarioChannel,
    ScenarioRedFlag,
    ScenarioStatus,
    ScenarioTactic,
    SimulatorScenario,
)


@pytest.fixture
def educator(db):
    return User.objects.create_user(
        email="educator_anticheat@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def five_published_scenarios(educator):
    scenarios = []
    for i in range(1, 6):
        is_scam = (i % 2 == 1)
        tactic = ScenarioTactic.URGENCY.value if is_scam else ScenarioTactic.NONE.value
        sc = SimulatorScenario.objects.create(
            title=f"Anti-Cheat Scenario {i}",
            channel=ScenarioChannel.SMS if is_scam else ScenarioChannel.EMAIL,
            is_scam=is_scam,
            tactic=tactic,
            difficulty=1,
            image_s3_key=f"scenarios/ac_{i}.png",
            image_alt=f"Alt text for scenario {i}",
            explanation=f"TOP SECRET EXPLANATION {i}",
            status=ScenarioStatus.PUBLISHED,
            author=educator,
        )
        if is_scam:
            ScenarioRedFlag.objects.create(
                scenario=sc,
                flag_code=RedFlagCode.MISMATCHED_DOMAIN.value,
                x_pct=10.0,
                y_pct=10.0,
                w_pct=20.0,
                h_pct=10.0,
                explanation=f"TOP SECRET HOTSPOT {i}",
            )
        scenarios.append(sc)
    return scenarios


@pytest.mark.django_db
class TestAntiCheatSchema:
    """
    TO BE PROVEN #20: Anti-cheat card masking.
    Assert scenario cards returned in attempt initialization strictly omit
    answers: is_scam, tactic, explanation, red_flags, flags.
    """

    def test_to_be_proven_20_attempt_init_never_leaks_answers(self, five_published_scenarios):
        client = APIClient()
        res = client.post("/api/v1/simulator/attempts/", data={}, format="json")
        assert res.status_code == 201
        data = res.json()

        scenarios = data.get("scenarios", [])
        assert len(scenarios) == 5

        allowed_keys = {"id", "title", "channel", "difficulty", "image_url", "image_alt"}
        forbidden_keys = {
            "is_scam",
            "tactic",
            "explanation",
            "red_flags",
            "flags",
            "hotspots",
            "answers",
            "correct_answer",
        }

        for card in scenarios:
            card_keys = set(card.keys())
            # Must only have allowed keys
            assert card_keys == allowed_keys, f"Card contains unexpected keys: {card_keys - allowed_keys}"

            # Must never contain any forbidden answer keys
            leaked_keys = card_keys.intersection(forbidden_keys)
            assert not leaked_keys, f"Anti-cheat violated! Leaked keys: {leaked_keys}"

            # Validate field values
            assert card["image_url"].startswith("/media/scenarios/")
            assert "TOP SECRET" not in str(card)
