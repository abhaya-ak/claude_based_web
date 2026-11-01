from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.db import connection

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.exceptions import ConflictError
from apps.intel.models import IndicatorType, VerifiedIndicator
from apps.intel.services.triage_service import verify_indicator
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
        email="analyst_conc@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


def create_report(ref: str, phone: str = "+60199991111") -> tuple[ScamReport, ReportIndicator]:
    report = ScamReport.objects.create(
        reference_code=ref,
        category=ScamCategory.PHISHING,
        platform=Platform.WHATSAPP,
        status=ReportStatus.PENDING,
        financial_loss=Decimal("50.00"),
        currency="MYR",
        message_text="Concurrent test report",
        country_code="MY",
    )
    ind = ReportIndicator.objects.create(
        report=report,
        type=IndicatorType.PHONE,
        raw_value=phone,
        normalized_value=phone,
        display_value=phone,
    )
    return report, ind


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_to_be_proven_12_deadlock_free_concurrent_cluster_verification(analyst_user):
    """
    Prove TO BE PROVEN #12: Deadlock-Free Concurrent Cluster Verification.
    Multiple worker threads simultaneously attempting to verify overlapping report
    clusters acquire locks strictly in monotonic ascending ScamReport.id order,
    preventing PostgreSQL deadlocks, correctly resolving reports, and preventing
    count double-counting.
    """
    # Create 4 pending reports sharing the same phone indicator
    shared_phone = "+60177778888"
    reports = [create_report(f"SCM-2026-CONC-{i}", phone=shared_phone) for i in range(4)]

    r1, ind1 = reports[0]
    r2, ind2 = reports[1]

    results = []

    def verify_worker(target_report_id, target_ind_id):
        # Explicitly close any old thread connection
        connection.close()
        try:
            res = verify_indicator(
                analyst=analyst_user,
                report_id=target_report_id,
                report_indicator_id=target_ind_id,
            )
            return ("SUCCESS", res)
        except ConflictError as e:
            return ("CONFLICT", str(e))
        except Exception as e:
            return ("ERROR", e)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(verify_worker, r1.id, ind1.id)
        f2 = executor.submit(verify_worker, r2.id, ind2.id)
        out1 = f1.result()
        out2 = f2.result()
        results.append(out1)
        results.append(out2)

    # Check for deadlocks or unexpected errors
    for status_type, val in results:
        assert status_type != "ERROR", f"Encountered unexpected error during concurrency: {val}"

    # Exactly one thread should succeed in resolving the 4-report cluster,
    # and the other thread should receive CONFLICT (report_already_resolved)
    statuses = [s for s, _ in results]
    assert "SUCCESS" in statuses
    assert "CONFLICT" in statuses

    # Verify that all 4 reports are VERIFIED
    for rep, _ in reports:
        rep.refresh_from_db()
        assert rep.status == ReportStatus.VERIFIED

    # Verify VerifiedIndicator total_report_count is exactly 4 (no double counting!)
    vi = VerifiedIndicator.objects.get(normalized_value=shared_phone)
    assert vi.total_report_count == 4
