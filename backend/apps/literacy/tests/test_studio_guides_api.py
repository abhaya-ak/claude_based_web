import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.enums import AudienceGroup
from apps.literacy.models import ContentStatus, EducationalGuide, Tactic


@pytest.fixture
def educator_a(db):
    return User.objects.create_user(
        email="educator_a@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_b(db):
    return User.objects.create_user(
        email="educator_b@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_literacy@scamshield.test",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen_literacy@scamshield.test",
        password="ValidPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def guide_a(educator_a):
    return EducationalGuide.objects.create(
        slug="educator-a-guide",
        title="Educator A's Guide",
        summary="A summary of Guide A",
        body="Body of Guide A",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.URGENCY.value],
        status=ContentStatus.DRAFT.value,
        author=educator_a,
    )


@pytest.mark.django_db
class TestStudioGuidesAPI:
    def test_educator_creates_draft_guide_with_unique_slug(self, educator_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        payload = {
            "title": "Spotting Phishing Scams",
            "summary": "How to recognize phishing attempts in email.",
            "body": "# Phishing Signs\n\nCheck the sender email address.",
            "audience_groups": [AudienceGroup.GENERAL.value],
            "tactics": [Tactic.URGENCY.value],
            "language": "en",
        }
        res1 = client.post("/api/v1/studio/guides/", payload, format="json")
        assert res1.status_code == 201
        assert res1.data["slug"] == "spotting-phishing-scams"
        assert res1.data["status"] == ContentStatus.DRAFT.value
        assert str(res1.data["author"]) == str(educator_a.id)

        # Duplicate title should generate unique collision-safe slug
        res2 = client.post("/api/v1/studio/guides/", payload, format="json")
        assert res2.status_code == 201
        assert res2.data["slug"] == "spotting-phishing-scams-2"

    def test_educator_lists_only_own_guides(self, educator_a, educator_b, guide_a):
        # Create guide for Educator B
        guide_b = EducationalGuide.objects.create(
            slug="educator-b-guide",
            title="Educator B's Guide",
            summary="A summary of Guide B",
            body="Body of Guide B",
            audience_groups=[AudienceGroup.GENERAL.value],
            tactics=[Tactic.FEAR.value],
            status=ContentStatus.DRAFT.value,
            author=educator_b,
        )

        client = APIClient()
        client.force_authenticate(user=educator_a)
        res = client.get("/api/v1/studio/guides/")
        assert res.status_code == 200
        guide_ids = [item["id"] for item in res.data["results"]]
        assert str(guide_a.id) in guide_ids
        assert str(guide_b.id) not in guide_ids

    def test_admin_lists_all_guides(self, admin_user, guide_a, educator_b):
        guide_b = EducationalGuide.objects.create(
            slug="educator-b-guide-2",
            title="Educator B's Guide 2",
            summary="A summary of Guide B 2",
            body="Body of Guide B 2",
            audience_groups=[AudienceGroup.GENERAL.value],
            tactics=[Tactic.FEAR.value],
            status=ContentStatus.DRAFT.value,
            author=educator_b,
        )
        client = APIClient()
        client.force_authenticate(user=admin_user)
        res = client.get("/api/v1/studio/guides/")
        assert res.status_code == 200
        guide_ids = [item["id"] for item in res.data["results"]]
        assert str(guide_a.id) in guide_ids
        assert str(guide_b.id) in guide_ids

    def test_to_be_proven_19_educator_cannot_edit_or_delete_other_educator_guide(
        self, educator_b, guide_a
    ):
        client = APIClient()
        client.force_authenticate(user=educator_b)

        # Attempt retrieve -> 403
        res_get = client.get(f"/api/v1/studio/guides/{guide_a.id}/")
        assert res_get.status_code == 403

        # Attempt patch -> 403
        res_patch = client.patch(
            f"/api/v1/studio/guides/{guide_a.id}/",
            {"title": "Tampered Title"},
            format="json",
        )
        assert res_patch.status_code == 403

        # Attempt delete -> 403
        res_del = client.delete(f"/api/v1/studio/guides/{guide_a.id}/")
        assert res_del.status_code == 403

    def test_admin_can_edit_and_delete_other_educator_guide(self, admin_user, guide_a):
        client = APIClient()
        client.force_authenticate(user=admin_user)

        res_patch = client.patch(
            f"/api/v1/studio/guides/{guide_a.id}/",
            {"title": "Admin Updated Title"},
            format="json",
        )
        assert res_patch.status_code == 200
        assert res_patch.data["title"] == "Admin Updated Title"

        res_del = client.delete(f"/api/v1/studio/guides/{guide_a.id}/")
        assert res_del.status_code == 204
        assert not EducationalGuide.objects.filter(id=guide_a.id).exists()

    def test_draft_only_delete_rule_published_or_archived_returns_409(self, educator_a, guide_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        # Publish guide
        client.post(f"/api/v1/studio/guides/{guide_a.id}/publish/")
        guide_a.refresh_from_db()
        assert guide_a.status == ContentStatus.PUBLISHED.value

        # Attempting to delete published guide must return 409 conflict
        res_del = client.delete(f"/api/v1/studio/guides/{guide_a.id}/")
        assert res_del.status_code == 409
        assert res_del.data["error"]["code"] == "guide_not_draft"

    def test_non_staff_users_cannot_access_studio(self, citizen_user, guide_a):
        client = APIClient()
        client.force_authenticate(user=citizen_user)

        assert client.get("/api/v1/studio/guides/").status_code == 403
        assert client.get(f"/api/v1/studio/guides/{guide_a.id}/").status_code == 403
        assert client.delete(f"/api/v1/studio/guides/{guide_a.id}/").status_code == 403
