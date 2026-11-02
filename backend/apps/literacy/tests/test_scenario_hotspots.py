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
def educator_a(db):
    return User.objects.create_user(
        email="educator_hotspot_a@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_b(db):
    return User.objects.create_user(
        email="educator_hotspot_b@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def scenario_scam(educator_a):
    return SimulatorScenario.objects.create(
        title="Hotspot Test Scam",
        channel=ScenarioChannel.EMAIL,
        is_scam=True,
        tactic=ScenarioTactic.AUTHORITY,
        difficulty=1,
        image_s3_key="scenarios/test-scam.png",
        image_alt="Test Alt",
        explanation="Test explanation",
        status=ScenarioStatus.DRAFT,
        author=educator_a,
    )


@pytest.fixture
def scenario_legit(educator_a):
    return SimulatorScenario.objects.create(
        title="Hotspot Test Legit",
        channel=ScenarioChannel.SMS,
        is_scam=False,
        tactic=ScenarioTactic.NONE,
        difficulty=1,
        image_s3_key="scenarios/test-legit.png",
        image_alt="Test Alt",
        explanation="Test explanation",
        status=ScenarioStatus.DRAFT,
        author=educator_a,
    )


@pytest.mark.django_db
class TestScenarioHotspotsAPI:
    def test_add_valid_hotspot(self, educator_a, scenario_scam):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        payload = {
            "flag_code": RedFlagCode.AUTHORITY_IMPERSONATION.value,
            "x_pct": "15.50",
            "y_pct": "25.00",
            "w_pct": "30.00",
            "h_pct": "10.00",
            "explanation": "Fake sender claims to be law enforcement.",
        }

        res = client.post(f"/api/v1/studio/scenarios/{scenario_scam.id}/flags/", data=payload, format="json")
        assert res.status_code == 201
        data = res.json()
        assert data["flag_code"] == RedFlagCode.AUTHORITY_IMPERSONATION.value
        assert float(data["x_pct"]) == 15.50
        assert float(data["y_pct"]) == 25.00
        assert float(data["w_pct"]) == 30.00
        assert float(data["h_pct"]) == 10.00
        assert data["explanation"] == "Fake sender claims to be law enforcement."

    def test_hotspot_coordinates_out_of_bounds_rejected(self, educator_a, scenario_scam):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        # x + w > 100
        payload = {
            "flag_code": RedFlagCode.SUSPICIOUS_LINK.value,
            "x_pct": "80.00",
            "y_pct": "10.00",
            "w_pct": "30.00",  # 80 + 30 = 110 > 100!
            "h_pct": "10.00",
            "explanation": "Out of bounds hotspot",
        }
        res = client.post(f"/api/v1/studio/scenarios/{scenario_scam.id}/flags/", data=payload, format="json")
        assert res.status_code == 400

        # y + h > 100
        payload["x_pct"] = "10.00"
        payload["w_pct"] = "10.00"
        payload["y_pct"] = "95.00"
        payload["h_pct"] = "10.00"  # 95 + 10 = 105 > 100!
        res = client.post(f"/api/v1/studio/scenarios/{scenario_scam.id}/flags/", data=payload, format="json")
        assert res.status_code == 400

        # w <= 0 or h <= 0
        payload["y_pct"] = "10.00"
        payload["w_pct"] = "0.00"
        payload["h_pct"] = "10.00"
        res = client.post(f"/api/v1/studio/scenarios/{scenario_scam.id}/flags/", data=payload, format="json")
        assert res.status_code == 400

    def test_cannot_add_hotspot_to_legitimate_scenario(self, educator_a, scenario_legit):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        payload = {
            "flag_code": RedFlagCode.SUSPICIOUS_LINK.value,
            "x_pct": "10.00",
            "y_pct": "10.00",
            "w_pct": "20.00",
            "h_pct": "20.00",
            "explanation": "Hotspot on legit scenario",
        }
        res = client.post(f"/api/v1/studio/scenarios/{scenario_legit.id}/flags/", data=payload, format="json")
        assert res.status_code == 400

    def test_delete_hotspot_and_ownership(self, educator_a, educator_b, scenario_scam):
        flag = ScenarioRedFlag.objects.create(
            scenario=scenario_scam,
            flag_code=RedFlagCode.THREAT_OF_LOSS,
            x_pct=5.0,
            y_pct=5.0,
            w_pct=20.0,
            h_pct=10.0,
            explanation="Threatens immediate arrest.",
        )

        client_b = APIClient()
        client_b.force_authenticate(user=educator_b)
        res = client_b.delete(f"/api/v1/studio/scenarios/{scenario_scam.id}/flags/{flag.id}/")
        assert res.status_code == 403

        client_a = APIClient()
        client_a.force_authenticate(user=educator_a)
        res = client_a.delete(f"/api/v1/studio/scenarios/{scenario_scam.id}/flags/{flag.id}/")
        assert res.status_code == 204
        assert not ScenarioRedFlag.objects.filter(id=flag.id).exists()
