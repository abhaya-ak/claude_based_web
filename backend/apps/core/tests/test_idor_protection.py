import hashlib
import uuid
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.enums import AudienceGroup
from apps.literacy.models import (
    ContentStatus,
    EducationalGuide,
    Language,
    RedFlagCode,
    ScenarioChannel,
    ScenarioRedFlag,
    ScenarioStatus,
    ScenarioTactic,
    SimulatorScenario,
    Tactic,
)
from apps.reports.models import PaymentMethod, Platform, ScamCategory, ScamReport


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def citizen_a(db):
    return User.objects.create_user(
        email="citizen_a@scamshield.test",
        password="Password123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_b(db):
    return User.objects.create_user(
        email="citizen_b@scamshield.test",
        password="Password123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_a(db):
    return User.objects.create_user(
        email="educator_a@scamshield.test",
        password="Password123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_b(db):
    return User.objects.create_user(
        email="educator_b@scamshield.test",
        password="Password123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestIdorProtection:
    def test_citizen_cannot_see_other_citizen_reports_in_reports_mine(
        self, api_client, citizen_a, citizen_b
    ):
        """
        IDOR Protection: /reports/mine/ filters strictly by request.user.
        Citizen A must NEVER see reports submitted by Citizen B.
        """
        report_a = ScamReport.objects.create(
            reporter=citizen_a,
            reference_code="SCM-2026-AAAA1111",
            category=ScamCategory.PHISHING,
            platform=Platform.WHATSAPP,
            country_code="MY",
            currency="MYR",
            financial_loss=Decimal("0.00"),
            payment_method=PaymentMethod.NONE,
            message_text="Citizen A report message",
        )
        report_b = ScamReport.objects.create(
            reporter=citizen_b,
            reference_code="SCM-2026-BBBB2222",
            category=ScamCategory.FAKE_JOB,
            platform=Platform.TELEGRAM,
            country_code="MY",
            currency="MYR",
            financial_loss=Decimal("0.00"),
            payment_method=PaymentMethod.NONE,
            message_text="Citizen B confidential report",
        )

        api_client.force_authenticate(user=citizen_a)
        res = api_client.get("/api/v1/reports/mine/")
        assert res.status_code == status.HTTP_200_OK
        results = res.json()["results"]
        references = [r["reference_code"] for r in results]

        assert report_a.reference_code in references
        assert report_b.reference_code not in references
        assert "BBBB2222" not in str(res.json())

    def test_cannot_track_report_with_wrong_access_key(self, api_client):
        """
        IDOR Protection: /reports/track/ requires exact hash match of access key.
        Using another report's key or a random key yields uniform 404.
        """
        rep1 = ScamReport.objects.create(
            reference_code="SCM-2026-TRACK111",
            is_anonymous=True,
            access_key_hash=hashlib.sha256(b"correct-key-1111").hexdigest(),
            category=ScamCategory.PHISHING,
            platform=Platform.SMS,
            country_code="MY",
            currency="MYR",
            financial_loss=Decimal("0.00"),
            payment_method=PaymentMethod.NONE,
            message_text="Report 1",
        )
        ScamReport.objects.create(
            reference_code="SCM-2026-TRACK222",
            is_anonymous=True,
            access_key_hash=hashlib.sha256(b"correct-key-2222").hexdigest(),
            category=ScamCategory.PHISHING,
            platform=Platform.SMS,
            country_code="MY",
            currency="MYR",
            financial_loss=Decimal("0.00"),
            payment_method=PaymentMethod.NONE,
            message_text="Report 2",
        )

        # 1. Valid key works
        ok_res = api_client.post(
            "/api/v1/reports/track/",
            {"reference_code": rep1.reference_code, "access_key": "correct-key-1111"},
            format="json",
        )
        assert ok_res.status_code == status.HTTP_200_OK

        # 2. Key from Report 2 cannot track Report 1
        idor_res = api_client.post(
            "/api/v1/reports/track/",
            {"reference_code": rep1.reference_code, "access_key": "correct-key-2222"},
            format="json",
        )
        assert idor_res.status_code == status.HTTP_404_NOT_FOUND

        # 3. Random key cannot track Report 1
        bad_res = api_client.post(
            "/api/v1/reports/track/",
            {"reference_code": rep1.reference_code, "access_key": "completely-wrong-key"},
            format="json",
        )
        assert bad_res.status_code == status.HTTP_404_NOT_FOUND

    def test_educator_cannot_edit_or_delete_other_educator_draft_guide(
        self, api_client, educator_a, educator_b
    ):
        """
        IDOR Protection: /studio/guides/<pk>/ enforces IsGuideAuthorOrAdmin.
        Educator B cannot edit or delete Educator A's guide.
        """
        guide = EducationalGuide.objects.create(
            title="Educator A Private Guide",
            slug=f"educator-a-private-guide-{uuid.uuid4().hex[:6]}",
            summary="Draft summary",
            body="Draft markdown body",
            audience_groups=[AudienceGroup.GENERAL],
            tactics=[Tactic.URGENCY.value],
            language=Language.EN,
            status=ContentStatus.DRAFT,
            author=educator_a,
        )

        # Educator B attempts PATCH
        api_client.force_authenticate(user=educator_b)
        patch_res = api_client.patch(
            f"/api/v1/studio/guides/{guide.id}/",
            {"title": "Hacked Guide Title"},
            format="json",
        )
        assert patch_res.status_code == status.HTTP_403_FORBIDDEN

        # Educator B attempts DELETE
        del_res = api_client.delete(f"/api/v1/studio/guides/{guide.id}/")
        assert del_res.status_code == status.HTTP_403_FORBIDDEN

        # Verify guide remains unchanged
        guide.refresh_from_db()
        assert guide.title == "Educator A Private Guide"

    def test_authenticated_user_cannot_access_other_user_simulator_attempt(
        self, api_client, citizen_a, citizen_b
    ):
        """
        IDOR Protection: User B cannot inspect, answer, or complete User A's simulator attempt.
        """
        # Create scenarios
        educator = User.objects.create_user(
            email="educator_sim_idor@scamshield.test",
            password="Password123!",
            role=Role.EDUCATOR,
            approval_status=ApprovalStatus.APPROVED,
        )
        scenarios = []
        for i in range(5):
            sc = SimulatorScenario.objects.create(
                title=f"Scenario {i+1}",
                channel=ScenarioChannel.SMS,
                is_scam=True,
                tactic=ScenarioTactic.URGENCY,
                difficulty=1,
                image_s3_key=f"scenarios/sim_{i+1}.png",
                image_alt="Prompt",
                explanation="Explanation",
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
                explanation="Flag",
            )
            scenarios.append(sc)

        # Citizen A creates attempt
        api_client.force_authenticate(user=citizen_a)
        create_res = api_client.post("/api/v1/simulator/attempts/", data={}, format="json")
        assert create_res.status_code == status.HTTP_201_CREATED
        attempt_id = create_res.json()["attempt_id"]

        # Citizen B attempts GET attempt
        api_client.force_authenticate(user=citizen_b)
        get_res = api_client.get(f"/api/v1/simulator/attempts/{attempt_id}/")
        assert get_res.status_code == status.HTTP_403_FORBIDDEN

        # Citizen B attempts to submit answer to Citizen A's attempt
        ans_res = api_client.post(
            f"/api/v1/simulator/attempts/{attempt_id}/answers/",
            data={
                "scenario_id": str(scenarios[0].id),
                "answered_is_scam": True,
                "selected_flag_code": RedFlagCode.SUSPICIOUS_LINK.value,
            },
            format="json",
        )
        assert ans_res.status_code == status.HTTP_403_FORBIDDEN

        # Citizen B attempts to complete Citizen A's attempt
        comp_res = api_client.post(
            f"/api/v1/simulator/attempts/{attempt_id}/complete/",
            data={},
            format="json",
        )
        assert comp_res.status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_user_cannot_access_other_session_simulator_attempt(self):
        """
        IDOR Protection: An anonymous player with Session Key Y cannot access an
        attempt created by Session Key X.
        """
        educator = User.objects.create_user(
            email="educator_anon_idor@scamshield.test",
            password="Password123!",
            role=Role.EDUCATOR,
            approval_status=ApprovalStatus.APPROVED,
        )
        for i in range(5):
            SimulatorScenario.objects.create(
                title=f"Scenario {i+1}",
                channel=ScenarioChannel.SMS,
                is_scam=True,
                tactic=ScenarioTactic.URGENCY,
                difficulty=1,
                image_s3_key=f"scenarios/anon_{i+1}.png",
                image_alt="Prompt",
                explanation="Explanation",
                status=ScenarioStatus.PUBLISHED,
                author=educator,
            )

        client_x = APIClient()
        session_x = str(uuid.uuid4())
        client_x.credentials(HTTP_X_SESSION_KEY=session_x)
        res_x = client_x.post("/api/v1/simulator/attempts/", data={}, format="json")
        assert res_x.status_code == status.HTTP_201_CREATED
        attempt_id = res_x.json()["attempt_id"]

        # Client Y attempts access
        client_y = APIClient()
        session_y = str(uuid.uuid4())
        client_y.credentials(HTTP_X_SESSION_KEY=session_y)
        res_y = client_y.get(f"/api/v1/simulator/attempts/{attempt_id}/")
        assert res_y.status_code == status.HTTP_403_FORBIDDEN

        # Client with no session key attempts access
        client_no_key = APIClient()
        res_no_key = client_no_key.get(f"/api/v1/simulator/attempts/{attempt_id}/")
        assert res_no_key.status_code == status.HTTP_403_FORBIDDEN

    def test_citizen_cannot_access_analyst_triage_or_admin_portal(self, api_client, citizen_a):
        """
        Role boundaries: Citizens cannot access Analyst queue or Admin audit logs.
        """
        api_client.force_authenticate(user=citizen_a)

        # Analyst queue
        triage_res = api_client.get("/api/v1/triage/queue/")
        assert triage_res.status_code == status.HTTP_403_FORBIDDEN

        # Admin audit logs
        audit_res = api_client.get("/api/v1/admin-portal/audit-logs/")
        assert audit_res.status_code == status.HTTP_403_FORBIDDEN
