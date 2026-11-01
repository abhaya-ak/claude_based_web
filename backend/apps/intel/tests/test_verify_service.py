from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.exceptions import ConflictError
from apps.intel.models import (
    IndicatorStatus,
    IndicatorType,
    ThreatLevel,
    TriageAction,
    TriageDecision,
)
from apps.intel.services.triage_service import threat_level_for, verify_indicator
from apps.reports.models import (
    Platform,
    ReportIndicator,
    ReportStatus,
    ScamCategory,
    ScamReport,
)


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_svc@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


def create_report_with_indicator(
    reference: str,
    indicator_type: str = IndicatorType.PHONE,
    raw_val: str = "+60123456789",
    norm_val: str = "+60123456789",
    status: str = ReportStatus.PENDING,
    category: str = ScamCategory.PHISHING,
) -> tuple[ScamReport, ReportIndicator]:
    report = ScamReport.objects.create(
        reference_code=reference,
        category=category,
        platform=Platform.WHATSAPP,
        status=status,
        financial_loss=Decimal("100.00"),
        currency="MYR",
        message_text="Scam message for " + reference,
        country_code="MY",
    )
    ind = ReportIndicator.objects.create(
        report=report,
        type=indicator_type,
        raw_value=raw_val,
        normalized_value=norm_val,
        display_value=raw_val,
    )
    return report, ind


@pytest.mark.django_db
class TestVerifyIndicatorService:
    def test_threat_level_thresholds(self):
        assert threat_level_for(1) == ThreatLevel.MEDIUM
        assert threat_level_for(2) == ThreatLevel.MEDIUM
        assert threat_level_for(3) == ThreatLevel.HIGH
        assert threat_level_for(9) == ThreatLevel.HIGH
        assert threat_level_for(10) == ThreatLevel.CRITICAL
        assert threat_level_for(25) == ThreatLevel.CRITICAL

    def test_verify_single_report(self, analyst_user):
        report, ind = create_report_with_indicator("SCM-2026-V1")

        result = verify_indicator(
            analyst=analyst_user,
            report_id=report.id,
            report_indicator_id=ind.id,
            public_note="Known phishing number",
        )

        vi = result["verified_indicator"]
        assert vi.type == ind.type
        assert vi.normalized_value == ind.normalized_value
        assert vi.total_report_count == 1
        assert vi.threat_level == ThreatLevel.MEDIUM
        assert vi.status == IndicatorStatus.ACTIVE
        assert vi.public_note == "Known phishing number"
        assert vi.verified_by == analyst_user

        # Report status
        report.refresh_from_db()
        assert report.status == ReportStatus.VERIFIED
        assert report.reviewed_by == analyst_user

        # Indicator linked
        ind.refresh_from_db()
        assert ind.verified_indicator == vi

        # Decision created
        decision = TriageDecision.objects.get(report=report)
        assert decision.action == TriageAction.VERIFY
        assert decision.indicator == vi
        assert decision.analyst == analyst_user

    def test_verify_cluster_of_three_reports_escalates_to_high(self, analyst_user):
        # 3 reports sharing same phone
        r1, ind1 = create_report_with_indicator("SCM-2026-CL01")
        r2, ind2 = create_report_with_indicator("SCM-2026-CL02")
        r3, ind3 = create_report_with_indicator("SCM-2026-CL03")

        result = verify_indicator(
            analyst=analyst_user,
            report_id=r1.id,
            report_indicator_id=ind1.id,
        )

        vi = result["verified_indicator"]
        assert vi.total_report_count == 3
        assert vi.threat_level == ThreatLevel.HIGH
        assert len(result["resolved_report_ids"]) == 3

        # All 3 reports must be VERIFIED
        for r in (r1, r2, r3):
            r.refresh_from_db()
            assert r.status == ReportStatus.VERIFIED
            assert r.reviewed_by == analyst_user

        # All 3 indicators must link to vi
        for ind in (ind1, ind2, ind3):
            ind.refresh_from_db()
            assert ind.verified_indicator == vi

        # 3 TriageDecision rows
        assert TriageDecision.objects.filter(indicator=vi).count() == 3

    def test_threat_escalation_to_critical_on_subsequent_cluster(self, analyst_user):
        # First verify cluster of 3 -> HIGH
        r1, ind1 = create_report_with_indicator("SCM-2026-T1")
        create_report_with_indicator("SCM-2026-T2")
        create_report_with_indicator("SCM-2026-T3")

        res1 = verify_indicator(
            analyst=analyst_user,
            report_id=r1.id,
            report_indicator_id=ind1.id,
        )
        assert res1["verified_indicator"].threat_level == ThreatLevel.HIGH
        assert res1["verified_indicator"].total_report_count == 3

        # Later, 7 more reports arrive with same phone
        new_reports = [create_report_with_indicator(f"SCM-2026-MORE-{i}") for i in range(7)]
        lead_report, lead_ind = new_reports[0]

        res2 = verify_indicator(
            analyst=analyst_user,
            report_id=lead_report.id,
            report_indicator_id=lead_ind.id,
        )
        vi = res2["verified_indicator"]
        vi.refresh_from_db()
        assert vi.total_report_count == 10
        assert vi.threat_level == ThreatLevel.CRITICAL

    def test_reverify_reactivates_revoked_indicator(self, analyst_user):
        r1, ind1 = create_report_with_indicator("SCM-2026-REVOKED1")
        res = verify_indicator(
            analyst=analyst_user,
            report_id=r1.id,
            report_indicator_id=ind1.id,
        )
        vi = res["verified_indicator"]
        # Manually revoke
        vi.status = IndicatorStatus.REVOKED
        vi.revoke_reason = "False alarm initially"
        vi.revoked_at = timezone.now()
        vi.save()

        # New report arrives with same indicator
        r2, ind2 = create_report_with_indicator("SCM-2026-REVOKED2")
        res2 = verify_indicator(
            analyst=analyst_user,
            report_id=r2.id,
            report_indicator_id=ind2.id,
        )
        vi2 = res2["verified_indicator"]
        vi2.refresh_from_db()
        assert vi2.id == vi.id
        assert vi2.status == IndicatorStatus.ACTIVE
        assert vi2.total_report_count == 2

    def test_verify_already_resolved_report_raises_conflict(self, analyst_user):
        r1, ind1 = create_report_with_indicator("SCM-2026-CONFLICT", status=ReportStatus.VERIFIED)

        with pytest.raises(ConflictError) as exc_info:
            verify_indicator(
                analyst=analyst_user,
                report_id=r1.id,
                report_indicator_id=ind1.id,
            )
        assert exc_info.value.detail == "Report has already been resolved."
