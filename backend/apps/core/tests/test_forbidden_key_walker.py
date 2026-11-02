import json
import uuid

import boto3
import pytest
from django.conf import settings
from django.utils import timezone
from moto import mock_aws
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.broadcasts.models import AdvisorySeverity, AdvisoryStatus, ThreatAdvisory
from apps.core.enums import AudienceGroup
from apps.intel.models import IndicatorStatus, IndicatorType, ThreatLevel, VerifiedIndicator
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
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog
from apps.reports.models import Platform, ScamCategory

FORBIDDEN_KEYS = {
    "raw_value",
    "reporter_id",
    "actor_ip",
    "actor_ip_hash",
    "access_key_hash",
    "s3_key",
    "password",
    "token_hash",
}


def assert_no_forbidden_keys(data, path=""):
    """
    Recursively walks any JSON structure (dict, list, primitive)
    and asserts that no forbidden key appears in dictionaries.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            assert key.lower() not in FORBIDDEN_KEYS, (
                f"Forbidden key '{key}' found at response path '{current_path}'"
            )
            assert_no_forbidden_keys(value, current_path)
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            assert_no_forbidden_keys(item, f"{path}[{idx}]")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestForbiddenKeyWalker:
    def test_lookup_endpoint_has_no_forbidden_keys(self, api_client):
        now = timezone.now()
        analyst = User.objects.create_user(
            email="analyst_lookup_fk@scamshield.test",
            password="TestPassword123!",
            role=Role.ANALYST,
        )
        VerifiedIndicator.objects.create(
            type=IndicatorType.PHONE,
            normalized_value="+60129998877",
            display_value="+60129998877",
            threat_level=ThreatLevel.HIGH,
            status=IndicatorStatus.ACTIVE,
            primary_category=ScamCategory.PHISHING,
            total_report_count=1,
            first_seen_at=now,
            last_seen_at=now,
            verified_at=now,
            verified_by=analyst,
        )
        response = api_client.post(
            "/api/v1/lookups/",
            {"query": "+60129998877"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert_no_forbidden_keys(response.json())

    def test_report_create_and_track_has_no_forbidden_keys(self, api_client):
        ind_json = json.dumps([{"type": IndicatorType.PHONE, "value": "+60129876543"}])
        submit_res = api_client.post(
            "/api/v1/reports/",
            data={
                "category": ScamCategory.PHISHING,
                "platform": Platform.WHATSAPP,
                "message_text": "Fake banking scam message asking for OTP code.",
                "country_code": "MY",
                "currency": "MYR",
                "financial_loss": "0.00",
                "indicators": ind_json,
            },
            format="multipart",
        )
        assert submit_res.status_code == status.HTTP_201_CREATED
        submit_data = submit_res.json()
        assert_no_forbidden_keys(submit_data)

        ref_code = submit_data["reference_code"]
        access_key = submit_data["access_key"]

        track_res = api_client.post(
            "/api/v1/reports/track/",
            {"reference_code": ref_code, "access_key": access_key},
            format="json",
        )
        assert track_res.status_code == status.HTTP_200_OK
        assert_no_forbidden_keys(track_res.json())

    def test_advisories_endpoints_have_no_forbidden_keys(self, api_client):
        analyst = User.objects.create_user(
            email="analyst_adv@scamshield.test",
            password="TestPassword123!",
            role=Role.ANALYST,
        )
        advisory = ThreatAdvisory.objects.create(
            title="Urgent Bank Phishing Wave",
            body="Detailed advisory body markdown text.",
            sms_text="Urgent bank phishing wave alert.",
            severity=AdvisorySeverity.CRITICAL,
            target_audience=AudienceGroup.GENERAL,
            category=ScamCategory.PHISHING,
            status=AdvisoryStatus.PUBLISHED,
            created_by=analyst,
        )

        list_res = api_client.get("/api/v1/advisories/")
        assert list_res.status_code == status.HTTP_200_OK
        assert_no_forbidden_keys(list_res.json())

        detail_res = api_client.get(f"/api/v1/advisories/{advisory.id}/")
        assert detail_res.status_code == status.HTTP_200_OK
        assert_no_forbidden_keys(detail_res.json())

    def test_guides_endpoints_have_no_forbidden_keys(self, api_client):
        educator = User.objects.create_user(
            email="educator_g@scamshield.test",
            password="TestPassword123!",
            role=Role.EDUCATOR,
        )
        guide = EducationalGuide.objects.create(
            title="How to Spot OTP Fraud",
            slug=f"how-to-spot-otp-fraud-{uuid.uuid4().hex[:6]}",
            summary="Essential guide for citizens against OTP theft.",
            body="# Protect Your OTP\nNever share OTP codes.",
            audience_groups=[AudienceGroup.GENERAL],
            tactics=[Tactic.URGENCY.value],
            language=Language.EN,
            status=ContentStatus.PUBLISHED,
            published_at=timezone.now(),
            author=educator,
        )

        list_res = api_client.get("/api/v1/guides/")
        assert list_res.status_code == status.HTTP_200_OK
        assert_no_forbidden_keys(list_res.json())

        detail_res = api_client.get(f"/api/v1/guides/{guide.slug}/")
        assert detail_res.status_code == status.HTTP_200_OK
        assert_no_forbidden_keys(detail_res.json())

    def test_simulator_endpoints_have_no_forbidden_keys(self):
        educator = User.objects.create_user(
            email="educator_fk@scamshield.test",
            password="ValidPassword123!",
            role=Role.EDUCATOR,
            approval_status=ApprovalStatus.APPROVED,
        )
        scenarios = []
        for i in range(5):
            sc = SimulatorScenario.objects.create(
                title=f"Scam Scenario {i+1}",
                channel=ScenarioChannel.SMS,
                is_scam=True,
                tactic=ScenarioTactic.URGENCY,
                difficulty=1,
                image_s3_key=f"scenarios/scam_{i+1}.png",
                image_alt=f"Prompt {i+1}",
                explanation=f"Explanation {i+1}",
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
                explanation=f"Flag {i+1}",
            )
            scenarios.append(sc)

        client = APIClient()
        session_key = str(uuid.uuid4())
        client.credentials(HTTP_X_SESSION_KEY=session_key)

        # 1. Init attempt
        init_res = client.post("/api/v1/simulator/attempts/", data={}, format="json")
        assert init_res.status_code == status.HTTP_201_CREATED
        init_data = init_res.json()
        assert_no_forbidden_keys(init_data)
        attempt_id = init_data["attempt_id"]

        # 2. Detail attempt
        det_res = client.get(f"/api/v1/simulator/attempts/{attempt_id}/")
        assert det_res.status_code == status.HTTP_200_OK
        assert_no_forbidden_keys(det_res.json())

        # 3. Answer scenarios
        for sc in scenarios:
            ans_res = client.post(
                f"/api/v1/simulator/attempts/{attempt_id}/answers/",
                data={
                    "scenario_id": str(sc.id),
                    "answered_is_scam": True,
                    "selected_flag_code": RedFlagCode.SUSPICIOUS_LINK.value,
                },
                format="json",
            )
            assert ans_res.status_code == status.HTTP_201_CREATED
            assert_no_forbidden_keys(ans_res.json())

        # 4. Complete attempt
        comp_res = client.post(
            f"/api/v1/simulator/attempts/{attempt_id}/complete/",
            data={},
            format="json",
        )
        assert comp_res.status_code == status.HTTP_200_OK
        assert_no_forbidden_keys(comp_res.json())

    def test_alert_subscription_has_no_forbidden_keys(self, api_client, monkeypatch):
        with mock_aws():
            sns = boto3.client("sns", region_name="ap-southeast-1")
            resp = sns.create_topic(Name="scamshield-alerts")
            monkeypatch.setattr(settings, "ALERTS_TOPIC_ARN", resp["TopicArn"])

            res = api_client.post(
                "/api/v1/alerts/subscriptions/",
                {"channel": "EMAIL", "endpoint": "subscriber_test@example.com", "audience": AudienceGroup.GENERAL},
                format="json",
            )
            assert res.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
            assert_no_forbidden_keys(res.json())

    def test_audit_log_viewer_truncates_actor_ip_hash(self, api_client):
        admin = User.objects.create_superuser(
            email="admin_audit_trunc@scamshield.test",
            password="AdminPassword123!",
            role=Role.ADMIN,
        )
        api_client.force_authenticate(user=admin)

        full_hash = "abcdef1234567890deadbeefcafe1234567890abcdef1234567890abcdef1234"
        SystemAuditLog.objects.create(
            event_type=AuditEventType.REPORT_SUBMITTED,
            actor=None,
            actor_ip_hash=full_hash,
            metadata={"test": "truncation"},
            severity=AuditSeverity.INFO,
        )

        res = api_client.get("/api/v1/admin-portal/audit-logs/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert "results" in data
        matching = [item for item in data["results"] if item.get("actor_ip_hash") is not None]
        assert len(matching) > 0
        for item in matching:
            assert item["actor_ip_hash"] == full_hash[:16]
            assert len(item["actor_ip_hash"]) == 16
            assert full_hash not in str(item)

        # CSV export test
        csv_res = api_client.get("/api/v1/admin-portal/audit-logs/export/")
        assert csv_res.status_code == status.HTTP_200_OK
        content = b"".join(csv_res.streaming_content).decode("utf-8")
        assert full_hash not in content
        assert full_hash[:16] in content
