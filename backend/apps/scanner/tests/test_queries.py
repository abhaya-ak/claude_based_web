import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role
from apps.accounts.tests.factories import UserFactory
from apps.reports.models import (
    IndicatorType,
    PaymentMethod,
    ReportIndicator,
    ReportStatus,
    ScamCategory,
    ScamReport,
)
from apps.scanner.models import HeuristicRule, RuleType
from apps.scanner.selectors.scanner_selectors import build_scan_payload
from apps.scanner.tests.factories import ScannerConfigFactory


@pytest.mark.django_db
class TestScannerQueryCounts:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.config = ScannerConfigFactory()

    def test_admin_portal_rules_list_query_count(self, django_assert_num_queries):
        """GET /api/v1/admin-portal/rules/ executes <= 3 queries (auth, count, select)."""
        rules = [
            HeuristicRule(
                rule_type=RuleType.KEYWORD,
                pattern=f"scamword{i}",
                weight=10,
                is_active=True,
                created_by=self.admin,
            )
            for i in range(15)
        ]
        HeuristicRule.objects.bulk_create(rules)

        with django_assert_num_queries(3, exact=False):
            resp = self.client.get("/api/v1/admin-portal/rules/")
            assert resp.status_code == 200
            assert resp.data["count"] >= 15

    def test_admin_portal_scanner_config_query_count(self, django_assert_num_queries):
        """GET /api/v1/admin-portal/scanner-config/ executes <= 2 queries (auth, select)."""
        with django_assert_num_queries(2, exact=False):
            resp = self.client.get("/api/v1/admin-portal/scanner-config/")
            assert resp.status_code == 200

    def test_dispatch_scan_payload_assembly_query_count(self, django_assert_num_queries):
        """dispatch_scan payload assembly executes <= 4 queries regardless of rule or indicator count."""
        rules = [
            HeuristicRule(
                rule_type=RuleType.KEYWORD,
                pattern=f"testword{i}",
                weight=5,
                is_active=True,
                created_by=self.admin,
            )
            for i in range(20)
        ]
        HeuristicRule.objects.bulk_create(rules)

        report = ScamReport.objects.create(
            reference_code=f"SCM-2026-{uuid.uuid4().hex[:8]}",
            category=ScamCategory.PHISHING,
            country_code="MY",
            currency="MYR",
            financial_loss=100,
            payment_method=PaymentMethod.BANK_TRANSFER,
            message_text="Urgent action required! Verify your account immediately at http://evil-phish.biz",
            platform="SMS",
            status=ReportStatus.PENDING,
        )
        indicators = [
            ReportIndicator(
                report=report,
                type=IndicatorType.URL,
                raw_value=f"http://phish{i}.biz",
                normalized_value=f"http://phish{i}.biz",
            )
            for i in range(5)
        ]
        ReportIndicator.objects.bulk_create(indicators)

        # Expected <= 4 queries:
        # 1: ScamReport with select_related / prefetch
        # 2: indicators prefetch
        # 3: HeuristicRule filter
        # 4: ReportIndicator aggregate count for prior pending
        with django_assert_num_queries(4, exact=False):
            payload = build_scan_payload(report.id)
            assert payload["report_id"] == str(report.id)
            assert len(payload["indicators"]) == 5
            assert len(payload["rules"]["KEYWORD"]) >= 20
