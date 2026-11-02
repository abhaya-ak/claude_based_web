import pytest
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.enums import AudienceGroup
from apps.literacy.models import AssetType, ContentStatus, EducationalGuide, GuideAsset, Tactic
from apps.literacy.selectors.guide_selectors import guides_for_tactics


@pytest.fixture
def educator(db):
    return User.objects.create_user(
        email="educator_queries@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def query_dataset(educator):
    now = timezone.now()
    guides = []
    for i in range(5):
        g = EducationalGuide.objects.create(
            slug=f"query-test-guide-{i}",
            title=f"Query Test Guide {i}",
            summary="Summary",
            body="Body content",
            audience_groups=[AudienceGroup.GENERAL.value],
            tactics=[Tactic.URGENCY.value],
            language="en",
            status=ContentStatus.PUBLISHED.value,
            published_at=now,
            author=educator,
        )
        # Create 2 assets per guide
        GuideAsset.objects.create(
            guide=g,
            asset_type=AssetType.IMAGE.value,
            s3_key=f"guides/{g.id}/img_{i}.png",
            content_type="image/png",
            size_bytes=1000,
            alt_text=f"Image {i}",
            sort_order=1,
        )
        GuideAsset.objects.create(
            guide=g,
            asset_type=AssetType.PDF.value,
            s3_key=f"guides/{g.id}/doc_{i}.pdf",
            content_type="application/pdf",
            size_bytes=2000,
            sort_order=2,
        )
        guides.append(g)
    return guides


@pytest.mark.django_db
class TestLiteracyQueryBounds:
    def test_public_guide_list_query_bound(self, query_dataset, django_db_blocker):
        client = APIClient()
        from django.db import connection

        with CaptureQueriesContext(connection) as ctx:
            response = client.get("/api/v1/guides/")

        assert response.status_code == 200
        assert len(response.data["results"]) == 5
        # 1 count query + 1 data query <= 3 queries (no N+1)
        assert len(ctx) <= 3, f"Expected <= 3 queries, got {len(ctx)}"

    def test_public_guide_detail_query_bound(self, query_dataset):
        client = APIClient()
        guide = query_dataset[0]
        from django.db import connection

        with CaptureQueriesContext(connection) as ctx:
            response = client.get(f"/api/v1/guides/{guide.slug}/")

        assert response.status_code == 200
        assert len(response.data["assets"]) == 2
        # 1 guide query + 1 prefetched assets query <= 2 queries
        assert len(ctx) <= 2, f"Expected <= 2 queries, got {len(ctx)}"

    def test_studio_guide_list_query_bound(self, educator, query_dataset):
        client = APIClient()
        client.force_authenticate(user=educator)
        from django.db import connection

        with CaptureQueriesContext(connection) as ctx:
            response = client.get("/api/v1/studio/guides/")

        assert response.status_code == 200
        assert len(response.data["results"]) == 5
        # 1 count query + 1 guide select_related("author") + 1 prefetched assets <= 3 queries
        assert len(ctx) <= 3, f"Expected <= 3 queries, got {len(ctx)}"

    def test_contract_selector_query_bound(self, query_dataset):
        from django.db import connection

        with CaptureQueriesContext(connection) as ctx:
            results = list(guides_for_tactics([Tactic.URGENCY.value], language="en"))

        assert len(results) == 5
        # Access assets on all guides to verify prefetch
        for guide in results:
            _ = [a.id for a in guide.assets.all()]

        # 1 guide query + 1 prefetched assets query <= 2 queries (0 N+1)
        assert len(ctx) <= 2, f"Expected <= 2 queries, got {len(ctx)}"
