import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.enums import AudienceGroup
from apps.literacy.models import ContentStatus, EducationalGuide, Tactic


@pytest.fixture
def educator(db):
    return User.objects.create_user(
        email="educator_lifecycle@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def other_educator(db):
    return User.objects.create_user(
        email="other_educator_lifecycle@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def draft_guide(educator):
    return EducationalGuide.objects.create(
        slug="lifecycle-test-guide",
        title="Lifecycle Test Guide",
        summary="A summary of the lifecycle test guide.",
        body="Full content of the guide.",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.URGENCY.value],
        status=ContentStatus.DRAFT.value,
        author=educator,
    )


@pytest.mark.django_db
class TestGuideLifecycle:
    def test_publish_requires_at_least_one_audience_group(self, educator):
        client = APIClient()
        client.force_authenticate(user=educator)

        # Create guide with empty audience groups
        guide = EducationalGuide.objects.create(
            slug="empty-audience-guide",
            title="Empty Audience Guide",
            summary="Summary",
            body="Body",
            audience_groups=[],
            tactics=[Tactic.URGENCY.value],
            status=ContentStatus.DRAFT.value,
            author=educator,
        )

        res = client.post(f"/api/v1/studio/guides/{guide.id}/publish/")
        assert res.status_code == 400
        assert res.data["error"]["code"] == "validation_error"

    def test_to_be_proven_19_published_at_is_set_once_and_invariant(self, educator, draft_guide):
        client = APIClient()
        client.force_authenticate(user=educator)

        # 1. First publish sets published_at
        res_pub1 = client.post(f"/api/v1/studio/guides/{draft_guide.id}/publish/")
        assert res_pub1.status_code == 200
        assert res_pub1.data["status"] == ContentStatus.PUBLISHED.value
        initial_published_at = res_pub1.data["published_at"]
        assert initial_published_at is not None

        draft_guide.refresh_from_db()
        assert draft_guide.status == ContentStatus.PUBLISHED.value
        assert draft_guide.published_at is not None

        # 2. Unpublish transitions to DRAFT
        res_unpub = client.post(f"/api/v1/studio/guides/{draft_guide.id}/unpublish/")
        assert res_unpub.status_code == 200
        assert res_unpub.data["status"] == ContentStatus.DRAFT.value
        draft_guide.refresh_from_db()
        assert draft_guide.status == ContentStatus.DRAFT.value

        # 3. Republish preserves original published_at
        res_pub2 = client.post(f"/api/v1/studio/guides/{draft_guide.id}/publish/")
        assert res_pub2.status_code == 200
        assert res_pub2.data["status"] == ContentStatus.PUBLISHED.value
        assert res_pub2.data["published_at"] == initial_published_at

    def test_archive_guide_workflow(self, educator, draft_guide):
        client = APIClient()
        client.force_authenticate(user=educator)

        res_archive = client.post(f"/api/v1/studio/guides/{draft_guide.id}/archive/")
        assert res_archive.status_code == 200
        assert res_archive.data["status"] == ContentStatus.ARCHIVED.value

        draft_guide.refresh_from_db()
        assert draft_guide.status == ContentStatus.ARCHIVED.value

    def test_other_educator_cannot_publish_unpublish_or_archive(self, other_educator, draft_guide):
        client = APIClient()
        client.force_authenticate(user=other_educator)

        assert client.post(f"/api/v1/studio/guides/{draft_guide.id}/publish/").status_code == 403
        assert client.post(f"/api/v1/studio/guides/{draft_guide.id}/unpublish/").status_code == 403
        assert client.post(f"/api/v1/studio/guides/{draft_guide.id}/archive/").status_code == 403
