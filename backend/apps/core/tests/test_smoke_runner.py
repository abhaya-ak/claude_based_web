import json
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.literacy.models import ScenarioChannel, ScenarioStatus, ScenarioTactic, SimulatorScenario
from apps.reports.models import IndicatorType, PaymentMethod, Platform, ScamCategory


@pytest.mark.django_db
def test_smoke_runner_in_process():
    """D151: Exercise all smoke test flows in-process via APIClient."""
    client = APIClient()

    # 1. Health check
    resp = client.get("/api/v1/health/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # 2. Readiness check
    resp = client.get("/api/v1/health/ready/")
    assert resp.status_code == 200
    assert resp.json()["database"] == "ok"

    # 3. Citizen registration & login
    email = "inprocess_smoke@scamshield.test"
    pwd = "P@ssword12345!Secure"
    resp = client.post(
        "/api/v1/auth/register/",
        {
            "email": email,
            "password": pwd,
            "full_name": "In-Process Citizen",
            "phone_number": "+977-9800000001",
        },
        format="json",
    )
    assert resp.status_code == 201

    resp = client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": pwd},
        format="json",
    )
    assert resp.status_code == 200
    token = resp.json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # 4. Scam report submission (multipart form fields per Phase 4 ReportCreateSerializer)
    idem_uuid = str(uuid.uuid4())
    indicators_json = json.dumps([
        {"type": IndicatorType.URL, "value": "http://scam-lottery-alert.top"},
        {"type": IndicatorType.PHONE, "value": "+60123456789"},
    ])
    report_data = {
        "category": ScamCategory.PHISHING,
        "platform": Platform.WHATSAPP,
        "message_text": "Guaranteed 500% weekly returns on crypto trading bot investment scheme.",
        "country_code": "MY",
        "currency": "MYR",
        "financial_loss": "0.00",
        "payment_method": PaymentMethod.NONE,
        "indicators": indicators_json,
    }
    resp = client.post(
        "/api/v1/reports/",
        data=report_data,
        format="multipart",
        HTTP_IDEMPOTENCY_KEY=idem_uuid,
    )
    assert resp.status_code == 201
    assert "reference_code" in resp.json()

    # 5. Public threat lookup
    client.credentials()  # Clear credentials for public endpoint check
    resp = client.post(
        "/api/v1/lookups/",
        {"query": "scam-lottery-alert.top"},
        format="json",
    )
    assert resp.status_code == 200
    assert "verdict" in resp.json()

    # 6. Simulator attempt creation
    # Provide 5 published scenarios so start_attempt succeeds
    author_user = User.objects.get(email=email)
    for i in range(5):
        SimulatorScenario.objects.create(
            title=f"Smoke Scenario {i}",
            channel=ScenarioChannel.EMAIL,
            is_scam=False,
            tactic=ScenarioTactic.NONE,
            difficulty=1,
            image_s3_key=f"scenarios/smoke_{i}.png",
            image_alt=f"Alt {i}",
            explanation=f"Explanation {i}",
            status=ScenarioStatus.PUBLISHED,
            author=author_user,
        )

    resp = client.post(
        "/api/v1/simulator/attempts/",
        {},
        format="json",
    )
    assert resp.status_code == 201
    assert "attempt_id" in resp.json()
