from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from rest_framework import exceptions

from apps.reports.models import ScamCategory, ScamReport

TACTIC_KEYWORDS = {
    "URGENCY": [
        "urgent",
        "immediate",
        "expire",
        "suspend",
        "otp",
        "act now",
        "verify",
        "click",
        "deadline",
        "fast",
    ],
    "AUTHORITY": [
        "police",
        "court",
        "officer",
        "lhdn",
        "bank",
        "bnm",
        "customs",
        "official",
        "maybank",
        "cimb",
        "touchngo",
        "ambank",
        "rhb",
        "public bank",
    ],
    "FEAR": [
        "arrest",
        "jail",
        "warrant",
        "legal",
        "lawsuit",
        "penalty",
        "freeze",
        "prosecut",
        "investigat",
        "block",
    ],
    "GREED": [
        "bonus",
        "prize",
        "reward",
        "guaranteed",
        "profit",
        "crypto",
        "investment",
        "job",
        "earn",
        "cashback",
        "win",
        "commission",
        "voucher",
    ],
}

CATEGORY_DEFAULT_TACTIC = {
    ScamCategory.PHISHING: "URGENCY",
    ScamCategory.IMPERSONATION: "AUTHORITY",
    ScamCategory.FAKE_JOB: "GREED",
    ScamCategory.ECOMMERCE_FRAUD: "GREED",
    ScamCategory.OTHER: "FEAR",
}


def validate_date_range(start_date: str | date | None, end_date: str | date | None) -> tuple[date, date]:
    """Validates date range bounds per D106.

    Defaults to trailing 30 days when omitted. Maximum span 90 days.
    """
    today = timezone.now().date()

    if not end_date:
        parsed_end = today
    elif isinstance(end_date, date):
        parsed_end = end_date
    else:
        try:
            parsed_end = datetime.strptime(str(end_date).strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise exceptions.ValidationError(
                {"end_date": "Invalid end_date format. Use YYYY-MM-DD."}, code="invalid_date"
            ) from exc

    if not start_date:
        parsed_start = parsed_end - timedelta(days=30)
    elif isinstance(start_date, date):
        parsed_start = start_date
    else:
        try:
            parsed_start = datetime.strptime(str(start_date).strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise exceptions.ValidationError(
                {"start_date": "Invalid start_date format. Use YYYY-MM-DD."}, code="invalid_date"
            ) from exc

    if parsed_start > parsed_end:
        raise exceptions.ValidationError(
            {"start_date": "start_date must be before or equal to end_date."},
            code="invalid_date_range",
        )

    if (parsed_end - parsed_start).days > 90:
        raise exceptions.ValidationError(
            {"date_range": "date range cannot exceed 90 days."},
            code="date_range_too_large",
        )

    return parsed_start, parsed_end


def get_volume_analytics(start_date: date, end_date: date) -> dict:
    """Pure ORM aggregation returning volume series by day, platform, and category per D106."""
    qs = ScamReport.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )

    by_day = [
        {"date": str(row["date"]), "count": row["count"]}
        for row in qs.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    ]

    total_reports = sum(row["count"] for row in by_day)

    by_platform = [
        {"platform": row["platform"], "count": row["count"]}
        for row in qs.values("platform").annotate(count=Count("id")).order_by("-count")
    ]

    by_category = [
        {"category": row["category"], "count": row["count"]}
        for row in qs.values("category").annotate(count=Count("id")).order_by("-count")
    ]

    series = [
        {
            "date": str(row["date"]),
            "platform": row["platform"],
            "category": row["category"],
            "count": row["count"],
        }
        for row in qs.annotate(date=TruncDate("created_at"))
        .values("date", "platform", "category")
        .annotate(count=Count("id"))
        .order_by("date")
    ]

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "total_reports": total_reports,
        "by_day": by_day,
        "by_platform": by_platform,
        "by_category": by_category,
        "series": series,
    }


def get_losses_analytics(start_date: date, end_date: date) -> list[dict]:
    """Pure ORM aggregation returning financial losses grouped by country_code, admin_area, and currency per D106."""
    qs = ScamReport.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )

    rows = (
        qs.values("country_code", "admin_area", "currency")
        .annotate(
            total_loss=Coalesce(Sum("financial_loss"), Decimal("0.00")),
            report_count=Count("id"),
        )
        .order_by("-total_loss")
    )

    return [
        {
            "country_code": row["country_code"],
            "admin_area": row["admin_area"],
            "currency": row["currency"],
            "total_loss": row["total_loss"],
            "report_count": row["report_count"],
        }
        for row in rows
    ]


def get_tactics_analytics(start_date: date, end_date: date) -> list[dict]:
    """Aggregates manipulation tactics from ScanResult.breakdown rule patterns and category fallbacks per D107."""
    reports = (
        ScamReport.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        .select_related("scan_result")
        .only("category", "scan_result__breakdown")
    )

    tactic_counts = {
        "URGENCY": 0,
        "AUTHORITY": 0,
        "FEAR": 0,
        "GREED": 0,
    }

    for rep in reports:
        matched_tactics = set()
        scan_res = getattr(rep, "scan_result", None)
        if scan_res and scan_res.breakdown:
            for item in scan_res.breakdown:
                pattern = str(item.get("rule", "")).lower()
                for tactic, kws in TACTIC_KEYWORDS.items():
                    if any(kw in pattern for kw in kws):
                        matched_tactics.add(tactic)

        if not matched_tactics:
            default_tactic = CATEGORY_DEFAULT_TACTIC.get(rep.category, "URGENCY")
            matched_tactics.add(default_tactic)

        for tactic in matched_tactics:
            tactic_counts[tactic] += 1

    return [
        {"tactic": tactic, "count": count}
        for tactic, count in sorted(tactic_counts.items(), key=lambda x: x[1], reverse=True)
    ]


def calculate_spike_status(
    last_24h_count: int,
    daily_avg: float,
    min_count: int = 5,
    growth_threshold: float = 3.0,
) -> tuple[bool, float | None]:
    """Pure helper calculating whether volume spike threshold is met per D107.

    Spike iff last_24h_count >= min_count AND (daily_avg == 0 or growth >= 3.0).
    """
    if daily_avg == 0.0:
        is_spike = last_24h_count >= min_count
        return is_spike, None

    growth_ratio = (last_24h_count - daily_avg) / daily_avg
    growth_pct = round(growth_ratio * 100.0, 1)
    is_spike = (last_24h_count >= min_count) and (growth_ratio >= growth_threshold)
    return is_spike, growth_pct


def get_spikes_analytics(
    reference_time: datetime | None = None,
    min_count: int = 5,
    growth_threshold: float = 3.0,
) -> list[dict]:
    """Compares report volume in last 24h vs trailing 7-day daily average per (platform, category) per D107."""
    if reference_time is None:
        reference_time = timezone.now()

    start_24h = reference_time - timedelta(hours=24)
    start_7d = reference_time - timedelta(days=8)

    # 24h report counts per (platform, category)
    counts_24h_qs = (
        ScamReport.objects.filter(
            created_at__gte=start_24h,
            created_at__lte=reference_time,
        )
        .values("platform", "category")
        .annotate(count=Count("id"))
    )
    counts_24h = {(r["platform"], r["category"]): r["count"] for r in counts_24h_qs}

    # Trailing 7d report counts per (platform, category)
    counts_7d_qs = (
        ScamReport.objects.filter(
            created_at__gte=start_7d,
            created_at__lt=start_24h,
        )
        .values("platform", "category")
        .annotate(count=Count("id"))
    )
    counts_7d = {(r["platform"], r["category"]): r["count"] for r in counts_7d_qs}

    all_keys = set(counts_24h.keys()) | set(counts_7d.keys())
    results = []

    for platform, category in all_keys:
        c_24h = counts_24h.get((platform, category), 0)
        c_7d = counts_7d.get((platform, category), 0)
        daily_avg = round(c_7d / 7.0, 2)

        is_spike, growth_pct = calculate_spike_status(
            c_24h,
            daily_avg,
            min_count=min_count,
            growth_threshold=growth_threshold,
        )

        results.append(
            {
                "platform": platform,
                "category": category,
                "last_24h_count": c_24h,
                "trailing_7d_count": c_7d,
                "daily_avg": daily_avg,
                "growth_pct": growth_pct,
                "is_spike": is_spike,
            }
        )

    return sorted(results, key=lambda x: (not x["is_spike"], -x["last_24h_count"]))
