from django.db.models import F
from django.db.models.expressions import RawSQL
from django.shortcuts import get_object_or_404

from apps.reports.models import ReportStatus, ScamReport

CLUSTER_SIZE_SQL = """
    SELECT COALESCE(NULLIF(COUNT(DISTINCT r2.id), 0), 1)
    FROM reports_reportindicator ri1
    JOIN reports_reportindicator ri2 
      ON ri2.type = ri1.type AND ri2.normalized_value = ri1.normalized_value
    JOIN reports_scamreport r2 
      ON r2.id = ri2.report_id AND r2.status = 'PENDING'
    WHERE ri1.report_id = reports_scamreport.id
"""


def get_triage_queue_queryset():
    """
    Returns pending ScamReport queryset annotated with cluster_size and
    ordered by risk_score DESC NULLS LAST, cluster_size DESC, created_at ASC, id ASC.
    """
    return (
        ScamReport.objects.filter(status=ReportStatus.PENDING)
        .annotate(cluster_size=RawSQL(CLUSTER_SIZE_SQL, ()))
        .order_by(
            F("risk_score").desc(nulls_last=True),
            F("cluster_size").desc(),
            F("created_at").asc(),
            F("id").asc(),
        )
    )


def get_report_detail(report_id):
    """
    Returns ScamReport instance for report_id annotated with cluster_size,
    prefetching indicators, evidence files, and scan_result.
    """
    qs = (
        ScamReport.objects.filter(id=report_id)
        .annotate(cluster_size=RawSQL(CLUSTER_SIZE_SQL, ()))
        .select_related("scan_result", "reviewed_by")
        .prefetch_related("indicators", "evidence")
    )
    return get_object_or_404(qs, id=report_id)
