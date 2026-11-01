from django.db import transaction
from django.http import Http404
from django.utils import timezone

from apps.core import audit, metrics
from apps.core.exceptions import ConflictError
from apps.intel.models import TriageAction, TriageDecision
from apps.reports.models import ReportStatus, ScamReport


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
