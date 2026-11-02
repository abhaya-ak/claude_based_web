import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.broadcasts.models import AdvisorySeverity, AdvisoryStatus, ThreatAdvisory
from apps.core.enums import AudienceGroup
from apps.reports.models import ScamCategory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_adv@example.com",
        password="ValidPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_user(db):
    return User.objects.create_user(
        email="educator_adv@example.com",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_adv@example.com",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_adv@example.com",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def draft_advisory(analyst_user):
    return ThreatAdvisory.objects.create(
        title="Draft Advisory: Fake Bank Campaign",
        body="Warning: Fake bank SMS messages are circulating asking for OTPs.",
        sms_text="Fake bank SMS circulating. Do not share OTPs.",
        severity=AdvisorySeverity.WARNING,
        target_audience=AudienceGroup.GENERAL,
        category=ScamCategory.PHISHING,
        status=AdvisoryStatus.DRAFT,
        created_by=analyst_user,
    )


@pytest.fixture
def published_advisory(analyst_user):
    now = timezone.now()
    return ThreatAdvisory.objects.create(
        title="Published Advisory: Impersonation Wave",
        body="Official Warning: Scammers posing as police officers demanding bail payments.",
        sms_text="Scam warning: Police never demand immediate cash transfers.",
        severity=AdvisorySeverity.CRITICAL,
        target_audience=AudienceGroup.ELDERLY,
        category=ScamCategory.IMPERSONATION,
        status=AdvisoryStatus.PUBLISHED,
        created_by=analyst_user,
        published_by=analyst_user,
        published_at=now,
        sns_message_id="msg-12345-published",
    )


@pytest.fixture
def failed_advisory(analyst_user):
    return ThreatAdvisory.objects.create(
        title="Failed Advisory: Investment Scheme",
        body="Warning: Fake telegram crypto investment groups promising 500% returns.",
        sms_text="Fake crypto investment alert.",
        severity=AdvisorySeverity.WARNING,
        target_audience="ALL",
        category=ScamCategory.FAKE_JOB,
        status=AdvisoryStatus.FAILED,
        created_by=analyst_user,
    )


@pytest.mark.django_db
class TestThreatAdvisoryPublicAccess:
    def test_public_list_shows_only_published_advisories(
        self, api_client, draft_advisory, published_advisory, failed_advisory
    ):
        res = api_client.get("/api/v1/advisories/")
        assert res.status_code == 200
        results = res.data.get("results", res.data)
        ids = [str(item["id"]) for item in results]
        assert str(published_advisory.id) in ids
        assert str(draft_advisory.id) not in ids
        assert str(failed_advisory.id) not in ids

    def test_public_list_serializer_omits_internal_staff_ids_and_sns_message_id(
        self, api_client, published_advisory
    ):
        res = api_client.get("/api/v1/advisories/")
        assert res.status_code == 200
        results = res.data.get("results", res.data)
        item = next(x for x in results if str(x["id"]) == str(published_advisory.id))
        assert "sns_message_id" not in item
        assert "created_by" not in item
        assert "published_by" not in item
        assert item["title"] == published_advisory.title
        assert item["severity"] == published_advisory.severity

    def test_public_detail_published_advisory_succeeds(self, api_client, published_advisory):
        res = api_client.get(f"/api/v1/advisories/{published_advisory.id}/")
        assert res.status_code == 200
        assert str(res.data["id"]) == str(published_advisory.id)
        assert "sns_message_id" not in res.data

    def test_public_detail_draft_advisory_returns_404(self, api_client, draft_advisory):
        res = api_client.get(f"/api/v1/advisories/{draft_advisory.id}/")
        assert res.status_code == 404
        assert res.data["error"]["code"] == "not_found"

    def test_public_detail_failed_advisory_returns_404(self, api_client, failed_advisory):
        res = api_client.get(f"/api/v1/advisories/{failed_advisory.id}/")
        assert res.status_code == 404
        assert res.data["error"]["code"] == "not_found"


@pytest.mark.django_db
class TestThreatAdvisoryStaffCRUD:
    def test_analyst_creates_draft_advisory(self, api_client, analyst_user):
        api_client.force_authenticate(user=analyst_user)
        payload = {
            "title": "New Emerging Threat: APK Malware",
            "body": "Malicious APK links circulating on messaging platforms. Never install outside store.",
            "sms_text": "Warning: Do not install APK files received via messaging apps.",
            "severity": AdvisorySeverity.CRITICAL,
            "target_audience": AudienceGroup.NON_TECH,
            "category": ScamCategory.PHISHING,
        }
        res = api_client.post("/api/v1/advisories/", payload, format="json")
        assert res.status_code == 201
        assert res.data["status"] == AdvisoryStatus.DRAFT
        assert res.data["title"] == payload["title"]
        assert ThreatAdvisory.objects.filter(id=res.data["id"]).exists()

    def test_analyst_creates_advisory_exceeding_body_limit_returns_400(self, api_client, analyst_user):
        api_client.force_authenticate(user=analyst_user)
        payload = {
            "title": "Invalid Advisory",
            "body": "A" * 1501,  # Exceeds max 1500 chars limit
            "severity": AdvisorySeverity.INFO,
            "target_audience": "ALL",
        }
        res = api_client.post("/api/v1/advisories/", payload, format="json")
        assert res.status_code == 400
        assert res.data["error"]["code"] == "validation_error"

    def test_analyst_patches_draft_advisory_succeeds(self, api_client, analyst_user, draft_advisory):
        api_client.force_authenticate(user=analyst_user)
        patch_payload = {
            "title": "Updated Draft Title: Urgent Bank Alert",
            "severity": AdvisorySeverity.CRITICAL,
        }
        res = api_client.patch(f"/api/v1/advisories/{draft_advisory.id}/", patch_payload, format="json")
        assert res.status_code == 200
        draft_advisory.refresh_from_db()
        assert draft_advisory.title == patch_payload["title"]
        assert draft_advisory.severity == AdvisorySeverity.CRITICAL

    def test_analyst_patches_published_advisory_returns_409_conflict(
        self, api_client, analyst_user, published_advisory
    ):
        api_client.force_authenticate(user=analyst_user)
        patch_payload = {"title": "Attempt to alter published advisory"}
        res = api_client.patch(f"/api/v1/advisories/{published_advisory.id}/", patch_payload, format="json")
        assert res.status_code == 409
        assert res.data["error"]["code"] in {"advisory_not_draft", "conflict"}

    def test_analyst_patches_failed_advisory_returns_409_conflict(
        self, api_client, analyst_user, failed_advisory
    ):
        api_client.force_authenticate(user=analyst_user)
        patch_payload = {"title": "Attempt to alter failed advisory"}
        res = api_client.patch(f"/api/v1/advisories/{failed_advisory.id}/", patch_payload, format="json")
        assert res.status_code == 409
        assert res.data["error"]["code"] in {"advisory_not_draft", "conflict"}

    def test_admin_cannot_create_or_patch_advisories(
        self, api_client, admin_user, draft_advisory
    ):
        api_client.force_authenticate(user=admin_user)
        # Create attempt
        res1 = api_client.post(
            "/api/v1/advisories/",
            {
                "title": "Admin Attempt",
                "body": "Admins should be read-only on advisories.",
                "severity": AdvisorySeverity.INFO,
                "target_audience": "ALL",
            },
            format="json",
        )
        assert res1.status_code == 403
        assert res1.data["error"]["code"] == "permission_denied"

        # Patch attempt
        res2 = api_client.patch(
            f"/api/v1/advisories/{draft_advisory.id}/",
            {"title": "Admin Edit Attempt"},
            format="json",
        )
        assert res2.status_code == 403
        assert res2.data["error"]["code"] == "permission_denied"

    def test_citizen_and_educator_cannot_create_or_patch(
        self, api_client, citizen_user, educator_user, draft_advisory
    ):
        for user in [citizen_user, educator_user]:
            api_client.force_authenticate(user=user)
            res1 = api_client.post("/api/v1/advisories/", {"title": "Test"}, format="json")
            assert res1.status_code == 403

            res2 = api_client.patch(f"/api/v1/advisories/{draft_advisory.id}/", {"title": "Edit"}, format="json")
            assert res2.status_code == 403

    def test_staff_list_filtering_by_status_category_severity(
        self, api_client, analyst_user, draft_advisory, published_advisory, failed_advisory
    ):
        api_client.force_authenticate(user=analyst_user)

        # Filter by status=DRAFT
        res = api_client.get("/api/v1/advisories/?status=DRAFT")
        assert res.status_code == 200
        ids = [str(item["id"]) for item in res.data["results"]]
        assert str(draft_advisory.id) in ids
        assert str(published_advisory.id) not in ids

        # Filter by category
        res = api_client.get(f"/api/v1/advisories/?category={ScamCategory.IMPERSONATION}")
        assert res.status_code == 200
        ids = [str(item["id"]) for item in res.data["results"]]
        assert str(published_advisory.id) in ids
        assert str(draft_advisory.id) not in ids

        # Filter by severity
        res = api_client.get(f"/api/v1/advisories/?severity={AdvisorySeverity.CRITICAL}")
        assert res.status_code == 200
        ids = [str(item["id"]) for item in res.data["results"]]
        assert str(published_advisory.id) in ids
        assert str(draft_advisory.id) not in ids
