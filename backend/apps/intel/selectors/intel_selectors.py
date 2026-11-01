from django.db.models import Count, Q, QuerySet

from apps.intel.models import IndicatorStatus, VerifiedIndicator
from apps.reports.models import ReportIndicator, ReportStatus


def find_active_indicators(pairs: list[tuple[str, str]]) -> QuerySet[VerifiedIndicator]:
    """Finds ACTIVE verified blacklist indicators for [(type, normalized_value), ...].

    Empty pairs returns .none() immediately without executing a database query.
    """
    if not pairs:
        return VerifiedIndicator.objects.none()

    q = Q()
    for itype, val in pairs:
        q |= Q(type=itype, normalized_value=val)

    return (
        VerifiedIndicator.objects.filter(status=IndicatorStatus.ACTIVE)
        .filter(q)
        .select_related("verified_by", "revoked_by")
    )


def count_pending_by_indicator(pairs: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """Returns count of distinct pending reports linked to each indicator pair.

    Executes a single aggregated query on ReportIndicator where report status is PENDING.
    Empty pairs returns {} immediately without executing a database query.
    """
    if not pairs:
        return {}

    q = Q()
    for itype, val in pairs:
        q |= Q(type=itype, normalized_value=val)

    rows = (
        ReportIndicator.objects.filter(report__status=ReportStatus.PENDING)
        .filter(q)
        .values("type", "normalized_value")
        .annotate(distinct_count=Count("report_id", distinct=True))
    )

    result = {(itype, val): 0 for itype, val in pairs}
    for row in rows:
        key = (row["type"], row["normalized_value"])
        if key in result:
            result[key] = row["distinct_count"]

    return result
