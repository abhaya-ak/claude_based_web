import io

import boto3
import pytest
from moto import mock_aws
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.aws import reset_clients
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

VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00" + b"\x00" * 64 + b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"


@pytest.fixture
def educator_a(db):
    return User.objects.create_user(
        email="educator_scenario_a@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_b(db):
    return User.objects.create_user(
        email="educator_scenario_b@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_scenario@scamshield.test",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_scenario@scamshield.test",
        password="ValidPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def s3_bucket():
    with mock_aws():
        reset_clients()
        s3 = boto3.client("s3", region_name="ap-southeast-1")
        s3.create_bucket(
            Bucket="scamshield-media-test",
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        yield s3
        reset_clients()


@pytest.fixture
def scenario_scam_draft(educator_a):
    return SimulatorScenario.objects.create(
        title="Fake Delivery SMS",
        channel=ScenarioChannel.SMS,
        is_scam=True,
        tactic=ScenarioTactic.URGENCY,
        difficulty=1,
        image_s3_key="scenarios/fake-delivery.png",
        image_alt="Fake parcel tracking link SMS",
        explanation="Urgent notice prompting click on phishing link.",
        status=ScenarioStatus.DRAFT,
        author=educator_a,
    )


@pytest.fixture
def scenario_legit_draft(educator_a):
    return SimulatorScenario.objects.create(
        title="Legitimate Bank Alert",
        channel=ScenarioChannel.EMAIL,
        is_scam=False,
        tactic=ScenarioTactic.NONE,
        difficulty=2,
        image_s3_key="scenarios/legit-bank.png",
        image_alt="Monthly bank e-statement notification",
        explanation="Standard advisory without urgent links or login prompts.",
        status=ScenarioStatus.DRAFT,
        author=educator_a,
    )


@pytest.mark.django_db
class TestStudioScenariosAPI:
    def test_educator_creates_draft_scenario_with_image(self, s3_bucket, educator_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        image_file = io.BytesIO(VALID_PNG_BYTES)
        image_file.name = "sms_scam.png"

        payload = {
            "title": "Suspicious Bank SMS",
            "channel": ScenarioChannel.SMS.value,
            "is_scam": True,
            "tactic": ScenarioTactic.URGENCY.value,
            "difficulty": 2,
            "image_alt": "SMS alleging account suspension with urgent link",
            "explanation": "Scammers manufacture artificial urgency to bypass scrutiny.",
            "image": image_file,
        }

        res = client.post("/api/v1/studio/scenarios/", data=payload, format="multipart")
        assert res.status_code == 201
        data = res.json()
        assert data["title"] == "Suspicious Bank SMS"
        assert data["channel"] == "SMS"
        assert data["is_scam"] is True
        assert data["tactic"] == "URGENCY"
        assert data["difficulty"] == 2
        assert data["status"] == "DRAFT"
        assert data["author_email"] == educator_a.email
        assert data["image_url"].startswith("/media/scenarios/")
        assert data["image_url"].endswith(".png")

        # Verify object exists in S3
        scenario_id = data["id"]
        scenario = SimulatorScenario.objects.get(id=scenario_id)
        s3_obj = s3_bucket.get_object(Bucket="scamshield-media-test", Key=scenario.image_s3_key)
        assert s3_obj["ContentType"] == "image/png"

    def test_spoofed_image_rejected(self, s3_bucket, educator_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        fake_image = io.BytesIO(b"Not a real image file, just plain text")
        fake_image.name = "malicious.png"

        payload = {
            "title": "Spoofed Image Scenario",
            "channel": ScenarioChannel.EMAIL.value,
            "is_scam": True,
            "tactic": ScenarioTactic.AUTHORITY.value,
            "difficulty": 1,
            "image_alt": "Alt text",
            "explanation": "Explanation",
            "image": fake_image,
        }

        res = client.post("/api/v1/studio/scenarios/", data=payload, format="multipart")
        assert res.status_code == 400

    def test_oversized_image_rejected(self, s3_bucket, educator_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        oversized_data = VALID_PNG_BYTES + (b"\x00" * (6 * 1024 * 1024))
        oversized_file = io.BytesIO(oversized_data)
        oversized_file.name = "huge.png"

        payload = {
            "title": "Huge Scenario",
            "channel": ScenarioChannel.EMAIL.value,
            "is_scam": True,
            "tactic": ScenarioTactic.FEAR.value,
            "difficulty": 1,
            "image_alt": "Alt text",
            "explanation": "Explanation",
            "image": oversized_file,
        }

        res = client.post("/api/v1/studio/scenarios/", data=payload, format="multipart")
        assert res.status_code in (400, 413)

    def test_legitimate_scenario_must_have_tactic_none(self, s3_bucket, educator_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        img = io.BytesIO(VALID_PNG_BYTES)
        img.name = "legit.png"

        payload = {
            "title": "Invalid Legit Scenario",
            "channel": ScenarioChannel.EMAIL.value,
            "is_scam": False,
            "tactic": ScenarioTactic.URGENCY.value,  # Invalid: legit must be NONE
            "difficulty": 1,
            "image_alt": "Alt text",
            "explanation": "Explanation",
            "image": img,
        }

        res = client.post("/api/v1/studio/scenarios/", data=payload, format="multipart")
        assert res.status_code == 400

    def test_scam_scenario_cannot_have_tactic_none(self, s3_bucket, educator_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        img = io.BytesIO(VALID_PNG_BYTES)
        img.name = "scam.png"

        payload = {
            "title": "Invalid Scam Scenario",
            "channel": ScenarioChannel.EMAIL.value,
            "is_scam": True,
            "tactic": ScenarioTactic.NONE.value,  # Invalid: scam must specify tactic
            "difficulty": 1,
            "image_alt": "Alt text",
            "explanation": "Explanation",
            "image": img,
        }

        res = client.post("/api/v1/studio/scenarios/", data=payload, format="multipart")
        assert res.status_code == 400

    def test_publish_scam_scenario_requires_at_least_one_red_flag(self, s3_bucket, educator_a, scenario_scam_draft):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        # 0 red flags -> publish should fail with 400
        res = client.post(f"/api/v1/studio/scenarios/{scenario_scam_draft.id}/publish/")
        assert res.status_code == 400
        assert "red_flags" in str(res.json())

        # Add 1 red flag
        ScenarioRedFlag.objects.create(
            scenario=scenario_scam_draft,
            flag_code=RedFlagCode.SUSPICIOUS_LINK,
            x_pct=10.0,
            y_pct=20.0,
            w_pct=30.0,
            h_pct=15.0,
            explanation="Unrecognized link domain.",
        )

        # Now publish succeeds
        res = client.post(f"/api/v1/studio/scenarios/{scenario_scam_draft.id}/publish/")
        assert res.status_code == 200
        assert res.json()["status"] == "PUBLISHED"

    def test_publish_legitimate_scenario_allows_zero_red_flags(self, s3_bucket, educator_a, scenario_legit_draft):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        # 0 red flags on legit scenario succeeds
        res = client.post(f"/api/v1/studio/scenarios/{scenario_legit_draft.id}/publish/")
        assert res.status_code == 200
        assert res.json()["status"] == "PUBLISHED"

    def test_unpublish_and_archive_lifecycle(self, s3_bucket, educator_a, scenario_legit_draft):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        client.post(f"/api/v1/studio/scenarios/{scenario_legit_draft.id}/publish/")
        scenario_legit_draft.refresh_from_db()
        assert scenario_legit_draft.status == ScenarioStatus.PUBLISHED

        # Unpublish
        res = client.post(f"/api/v1/studio/scenarios/{scenario_legit_draft.id}/unpublish/")
        assert res.status_code == 200
        assert res.json()["status"] == "DRAFT"

        # Archive
        res = client.post(f"/api/v1/studio/scenarios/{scenario_legit_draft.id}/archive/")
        assert res.status_code == 200
        assert res.json()["status"] == "ARCHIVED"

    def test_educator_ownership_and_admin_bypass(self, s3_bucket, educator_a, educator_b, admin_user, scenario_scam_draft):
        client_b = APIClient()
        client_b.force_authenticate(user=educator_b)

        # Educator B cannot view Educator A's scenario
        res = client_b.get(f"/api/v1/studio/scenarios/{scenario_scam_draft.id}/")
        assert res.status_code == 403

        # Educator B cannot update Educator A's scenario
        res = client_b.patch(f"/api/v1/studio/scenarios/{scenario_scam_draft.id}/", {"title": "Hacked Title"})
        assert res.status_code == 403

        # Educator B cannot delete Educator A's scenario
        res = client_b.delete(f"/api/v1/studio/scenarios/{scenario_scam_draft.id}/")
        assert res.status_code == 403

        # Admin can view and update
        client_admin = APIClient()
        client_admin.force_authenticate(user=admin_user)
        res = client_admin.get(f"/api/v1/studio/scenarios/{scenario_scam_draft.id}/")
        assert res.status_code == 200
        assert res.json()["title"] == scenario_scam_draft.title

    def test_non_staff_role_rejected(self, s3_bucket, citizen_user):
        client = APIClient()
        client.force_authenticate(user=citizen_user)

        res = client.get("/api/v1/studio/scenarios/")
        assert res.status_code == 403

    def test_delete_answered_scenario_raises_409_conflict(self, s3_bucket, educator_a, scenario_scam_draft):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        # Create attempt and answer referencing this scenario
        attempt = SimulatorAttempt.objects.create(
            user=educator_a,
            scenario_ids=[scenario_scam_draft.id] * 5,
            status=AttemptStatus.IN_PROGRESS,
        )
        AttemptAnswer.objects.create(
            attempt=attempt,
            scenario=scenario_scam_draft,
            answered_is_scam=True,
            selected_flag_code=None,
            is_correct=False,
        )

        # Attempting to delete scenario with answers returns 409 Conflict
        res = client.delete(f"/api/v1/studio/scenarios/{scenario_scam_draft.id}/")
        assert res.status_code == 409
        data = res.json()
        assert "answers" in str(data) or data.get("error", {}).get("code") in ("scenario_has_answers", "conflict")
