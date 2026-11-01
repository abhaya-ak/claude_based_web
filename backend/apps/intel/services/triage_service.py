from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.http import Http404
from django.utils import timezone

from apps.core import audit, metrics
from apps.core.exceptions import ConflictError
from apps.intel.models import (
    IndicatorStatus,
    ThreatLevel,
    TriageAction,
    TriageDecision,
    VerifiedIndicator,
)
from apps.reports.models import ReportIndicator, ReportStatus, ScamReport


def threat_level_for(count: int) -> str:
    """1-2 MEDIUM, 3-9 HIGH, 10+ CRITICAL per Phase 6 specification."""
    if count >= 10:
        return ThreatLevel.CRITICAL
    if count >= 3:
        return ThreatLevel.HIGH
    return ThreatLevel.MEDIUM


@transaction.atomic
def reject_report(*, report_id, analyst, reason: str, ip_hash: str = "") -> ScamReport:
    """
    Rejects a pending ScamReport, records TriageDecision(action='REJECT'),
    audits REPORT_REJECTED, and emits ReportsRejected metric on commit.
    """
    try:
        report = ScamReport.objects.select_for_update().get(id=report_id)
    except ScamReport.DoesNotExist:
        raise Http404("Report not found.") from None

    if report.status != ReportStatus.PENDING:
        raise ConflictError(
            detail="Report has already been resolved.",
            code="report_already_resolved",
        )

    now = timezone.now()
    report.status = ReportStatus.REJECTED
    report.reviewed_by = analyst
    report.reviewed_at = now
    report.review_note = reason
    report.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

    TriageDecision.objects.create(
        report=report,
        analyst=analyst,
        action=TriageAction.REJECT,
        reason=reason,
    )

    audit.log_event(
        "REPORT_REJECTED",
        actor=analyst,
        target=report,
        ip_hash=ip_hash,
        metadata={"category": report.category},
    )

    transaction.on_commit(lambda: metrics.emit("ReportsRejected"))

    return report


@transaction.atomic
def verify_indicator(
    *,
    analyst,
    report_id,
    report_indicator_id,
    public_note: str = "",
    ip_hash: str = "",
) -> dict:
    """
    Verifies a cluster of pending scam reports sharing the target indicator.
    Acquires row locks in monotonic ascending id order to prevent deadlocks (TO BE PROVEN #12).
    Re-verifies primary report is still PENDING under lock.
    Upserts VerifiedIndicator, reactivates if REVOKED, marks reports VERIFIED,
    links indicators, records TriageDecisions, audits event, and emits metric on commit.
    """
    try:
        src = (
            ReportIndicator.objects.select_related("report")
            .filter(id=report_indicator_id, report_id=report_id)
            .first()
        )
    except Exception:
        src = None

    if not src:
        raise Http404("Report indicator not found.")

    if src.report.status != ReportStatus.PENDING:
        raise ConflictError(
            detail="Report has already been resolved.",
            code="report_already_resolved",
        )

    # Find all candidate ScamReport IDs sharing (type, normalized_value)
    candidate_ids = set(
        ScamReport.objects.filter(
            status=ReportStatus.PENDING,
            indicators__type=src.type,
            indicators__normalized_value=src.normalized_value,
        )
        .values_list("id", flat=True)
        .distinct()
    )
    candidate_ids.add(report_id)

    # Acquire row locks in monotonic ascending id order to prevent deadlocks (TO BE PROVEN #12)
    locked_reports = list(
        ScamReport.objects.select_for_update().filter(id__in=candidate_ids).order_by("id")
    )

    # Locate primary report under lock
    primary_report = next((r for r in locked_reports if r.id == report_id), None)
    if not primary_report or primary_report.status != ReportStatus.PENDING:
        raise ConflictError(
            detail="Report has already been resolved.",
            code="report_already_resolved",
        )

    # Filter reports that are still PENDING
    cluster_reports = [r for r in locked_reports if r.status == ReportStatus.PENDING]
    n = len(cluster_reports)
    if n == 0:
        raise ConflictError(
            detail="Report has already been resolved.",
            code="report_already_resolved",
        )

    now = timezone.now()
    newest = max(r.created_at for r in cluster_reports)
    oldest = min(r.created_at for r in cluster_reports)

    # Upsert and lock VerifiedIndicator
    vi, created = VerifiedIndicator.objects.select_for_update().get_or_create(
        type=src.type,
        normalized_value=src.normalized_value,
        defaults=dict(
            display_value=src.display_value,
            primary_category=src.report.category,
            total_report_count=n,
            first_seen_at=oldest,
            last_seen_at=newest,
            threat_level=threat_level_for(n),
            status=IndicatorStatus.ACTIVE,
            public_note=public_note,
            verified_by=analyst,
            verified_at=now,
        ),
    )

    if not created:
        update_fields = {
            "total_report_count": F("total_report_count") + n,
            "last_seen_at": Greatest(F("last_seen_at"), newest),
            "status": IndicatorStatus.ACTIVE,
            "updated_at": now,
        }
        if public_note:
            update_fields["public_note"] = public_note
        VerifiedIndicator.objects.filter(pk=vi.pk).update(**update_fields)
        vi.refresh_from_db()
        new_threat = threat_level_for(vi.total_report_count)
        VerifiedIndicator.objects.filter(pk=vi.pk).update(threat_level=new_threat)
        vi.threat_level = new_threat

    resolved_ids = [r.id for r in cluster_reports]

    # Mark all reports VERIFIED
    ScamReport.objects.filter(id__in=resolved_ids).update(
        status=ReportStatus.VERIFIED,
        reviewed_by=analyst,
        reviewed_at=now,
        review_note=public_note,
        updated_at=now,
    )

    # Link matching ReportIndicators to vi
    ReportIndicator.objects.filter(
        report_id__in=resolved_ids,
        type=src.type,
        normalized_value=src.normalized_value,
    ).update(verified_indicator=vi)

    # Create TriageDecision for each verified report
    TriageDecision.objects.bulk_create(
        [
            TriageDecision(
                report=r,
                analyst=analyst,
                action=TriageAction.VERIFY,
                indicator=vi,
            )
            for r in cluster_reports
        ]
    )

    # Audit log
    audit.log_event(
        "INDICATOR_VERIFIED",
        actor=analyst,
        target=vi,
        ip_hash=ip_hash,
        metadata={
            "report_id": str(report_id),
            "cluster_size": n,
            "threat_level": vi.threat_level,
        },
    )

    # Metric on commit
    transaction.on_commit(lambda: metrics.emit("IndicatorsVerified"))

    return {
        "verified_indicator": vi,
        "resolved_report_ids": [str(rid) for rid in resolved_ids],
        "cluster_size": n,
        "threat_level": vi.threat_level,
    }
