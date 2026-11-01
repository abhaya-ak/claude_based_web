from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.reports.models import (
    IndicatorType,
    Platform,
    ReportIndicator,
    ReportStatus,
    ScamCategory,
    ScamReport,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@scamshield.gov",
        password="TestPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def citizen_user(db):
    return User.objects.create_user(
        email="citizen@example.com",
        password="TestPassword123!",
        role=Role.CITIZEN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_user(db):
    return User.objects.create_user(
        email="educator@example.com",
        password="TestPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def unapproved_analyst(db):
    return User.objects.create_user(
        email="pending_analyst@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.PENDING,
    )


def create_test_report(
    reference: str,
    status: str = ReportStatus.PENDING,
    platform: str = Platform.WHATSAPP,
    category: str = ScamCategory.PHISHING,
    risk_score: int | None = None,
    is_high_priority: bool = False,
    created_at=None,
    indicators: list[tuple[str, str, str]] | None = None,
) -> ScamReport:
    report = ScamReport.objects.create(
        reference_code=reference,
        category=category,
        platform=platform,
        status=status,
        financial_loss=Decimal("150.00"),
        currency="MYR",
        message_text="Scam text for " + reference,
        country_code="MY",
        risk_score=risk_score,
        is_high_priority=is_high_priority,
    )
    if created_at:
        ScamReport.objects.filter(id=report.id).update(created_at=created_at)
        report.refresh_from_db()

    if indicators:
        for ind_type, raw_val, norm_val in indicators:
            ReportIndicator.objects.create(
                report=report,
                type=ind_type,
                raw_value=raw_val,
                normalized_value=norm_val,
                display_value=raw_val,
            )
    return report


@pytest.mark.django_db
class TestTriageQueueAPI:
    url = "/api/v1/triage/queue/"

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == 401
        assert "error" in resp.json()

    def test_citizen_and_educator_return_403(self, api_client, citizen_user, educator_user):
        api_client.force_authenticate(user=citizen_user)
        resp = api_client.get(self.url)
        assert resp.status_code == 403

        api_client.force_authenticate(user=educator_user)
        resp = api_client.get(self.url)
        assert resp.status_code == 403

    def test_unapproved_analyst_returns_403(self, api_client, unapproved_analyst):
        api_client.force_authenticate(user=unapproved_analyst)
        resp = api_client.get(self.url)
        assert resp.status_code == 403

    def test_analyst_and_admin_return_200(self, api_client, analyst_user, admin_user):
        create_test_report("SCM-2026-PENDING1", status=ReportStatus.PENDING)

        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get(self.url)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 1

        api_client.force_authenticate(user=admin_user)
        resp = api_client.get(self.url)
        assert resp.status_code == 200

    def test_queue_excludes_verified_and_rejected_reports(self, api_client, analyst_user):
        create_test_report("SCM-2026-PEND1", status=ReportStatus.PENDING)
        create_test_report("SCM-2026-VER1", status=ReportStatus.VERIFIED)
        create_test_report("SCM-2026-REJ1", status=ReportStatus.REJECTED)

        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get(self.url)
        assert resp.status_code == 200
        refs = [r["reference_code"] for r in resp.json()["results"]]
        assert refs == ["SCM-2026-PEND1"]

    def test_cluster_size_annotation_and_shared_indicators(self, api_client, analyst_user):
        shared_phone = (IndicatorType.PHONE, "+60123456789", "+60123456789")
        other_phone = (IndicatorType.PHONE, "+60199999999", "+60199999999")

        # 3 reports sharing shared_phone
        create_test_report("SCM-2026-C1", indicators=[shared_phone])
        create_test_report("SCM-2026-C2", indicators=[shared_phone])
        create_test_report("SCM-2026-C3", indicators=[shared_phone, other_phone])
        # 1 report with other_phone only
        create_test_report("SCM-2026-C4", indicators=[other_phone])
        # 1 isolated report with no shared indicator
        create_test_report("SCM-2026-ISOLATED", indicators=[(IndicatorType.EMAIL, "a@b.com", "a@b.com")])

        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get(self.url)
        assert resp.status_code == 200
        results_by_ref = {r["reference_code"]: r for r in resp.json()["results"]}

        # r1, r2 share shared_phone with r3 (which also has other_phone shared with r4)
        # r1 shares with r2, r3 -> cluster size at least 3
        assert results_by_ref["SCM-2026-C1"]["cluster_size"] >= 3
        assert results_by_ref["SCM-2026-C2"]["cluster_size"] >= 3
        # r5 is isolated -> cluster size exactly 1
        assert results_by_ref["SCM-2026-ISOLATED"]["cluster_size"] == 1

    def test_queue_ordering(self, api_client, analyst_user):
        now = timezone.now()
        shared_ind = (IndicatorType.URL, "https://phish.com", "https://phish.com")

        # r_high: score 80
        create_test_report("SCM-2026-HIGH", risk_score=80, created_at=now - timedelta(hours=5))
        # r_cluster_1 and r_cluster_2: score 50, cluster size 2
        create_test_report("SCM-2026-CL1", risk_score=50, indicators=[shared_ind], created_at=now - timedelta(hours=3))
        create_test_report("SCM-2026-CL2", risk_score=50, indicators=[shared_ind], created_at=now - timedelta(hours=2))
        # r_single: score 50, cluster size 1
        create_test_report("SCM-2026-SINGLE", risk_score=50, created_at=now - timedelta(hours=4))
        # r_null_score: score None
        create_test_report("SCM-2026-NOSCORE", risk_score=None, created_at=now - timedelta(hours=10))

        api_client.force_authenticate(user=analyst_user)
        resp = api_client.get(self.url)
        assert resp.status_code == 200
        refs = [r["reference_code"] for r in resp.json()["results"]]

        # SCM-2026-HIGH (score 80) must be first
        assert refs[0] == "SCM-2026-HIGH"
        # Among score 50: CL1 and CL2 (cluster_size 2) come before SINGLE (cluster_size 1)
        cl_indices = [refs.index("SCM-2026-CL1"), refs.index("SCM-2026-CL2")]
        single_idx = refs.index("SCM-2026-SINGLE")
        assert max(cl_indices) < single_idx
        # Between CL1 and CL2 (same score 50, same cluster_size 2): older created_at comes first (CL1)
        assert refs.index("SCM-2026-CL1") < refs.index("SCM-2026-CL2")
        # NULL score comes last
        assert refs[-1] == "SCM-2026-NOSCORE"

    def test_queue_filters(self, api_client, analyst_user):
        create_test_report("SCM-2026-F1", platform=Platform.TELEGRAM, category=ScamCategory.FAKE_JOB, risk_score=85, is_high_priority=True)
        create_test_report("SCM-2026-F2", platform=Platform.WHATSAPP, category=ScamCategory.PHISHING, risk_score=40, is_high_priority=False)

        api_client.force_authenticate(user=analyst_user)

        # Filter by platform
        resp = api_client.get(self.url + "?platform=TELEGRAM")
        assert resp.status_code == 200
        assert [r["reference_code"] for r in resp.json()["results"]] == ["SCM-2026-F1"]

        # Filter by category
        resp = api_client.get(self.url + "?category=PHISHING")
        assert resp.status_code == 200
        assert [r["reference_code"] for r in resp.json()["results"]] == ["SCM-2026-F2"]

        # Filter by is_high_priority
        resp = api_client.get(self.url + "?is_high_priority=true")
        assert resp.status_code == 200
        assert [r["reference_code"] for r in resp.json()["results"]] == ["SCM-2026-F1"]

        # Filter by min_risk_score
        resp = api_client.get(self.url + "?min_risk_score=80")
        assert resp.status_code == 200
        assert [r["reference_code"] for r in resp.json()["results"]] == ["SCM-2026-F1"]

    def test_queue_invalid_filters_returns_400(self, api_client, analyst_user):
        api_client.force_authenticate(user=analyst_user)

        resp = api_client.get(self.url + "?platform=INVALID_PLATFORM")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "validation_error"

        resp = api_client.get(self.url + "?category=INVALID_CAT")
        assert resp.status_code == 400

        resp = api_client.get(self.url + "?is_high_priority=notabool")
        assert resp.status_code == 400

        resp = api_client.get(self.url + "?min_risk_score=150")
        assert resp.status_code == 400

        resp = api_client.get(self.url + "?min_risk_score=-5")
        assert resp.status_code == 400

    def test_queue_query_count_bounded(self, api_client, analyst_user, django_assert_num_queries):
        for i in range(15):
            create_test_report(
                f"SCM-2026-Q{i:02d}",
                risk_score=i * 5,
                indicators=[(IndicatorType.PHONE, f"+6012000{i:04d}", f"+6012000{i:04d}")],
            )

        api_client.force_authenticate(user=analyst_user)
        # Should execute <= 3 queries: (1) COUNT, (2) SELECT with annotations and joins
        with django_assert_num_queries(2):
            resp = api_client.get(self.url)
            assert resp.status_code == 200
            assert len(resp.json()["results"]) == 15
