import uuid
from urllib.parse import urlsplit

from django.db.models import Count, Q

from apps.reports.models import ReportIndicator, ReportStatus, ScamReport
from apps.scanner.models import HeuristicRule, ScannerConfig


def extract_host(indicator_type: str, normalized_val: str) -> str:
    """Extracts lowercase hostname from URL or DOMAIN indicator values."""
    if indicator_type not in ("URL", "DOMAIN"):
        return ""
    val = (normalized_val or "").strip()
    if not val:
        return ""
    if indicator_type == "DOMAIN":
        # Strip path or port if present
        host = val.split("/")[0].split(":")[0].strip().lower()
        return host

    # URL indicator
    if not (val.startswith("http://") or val.startswith("https://")):
        val = "//" + val
    parsed = urlsplit(val)
    host = (parsed.hostname or "").strip().lower()
    return host


def build_scan_payload(report_id: uuid.UUID) -> dict:
    """
    Builds the payload for Lambda heuristic scanning in <= 4 lean queries.
    Contract 3.5: report text, indicators, rules, config, ruleset_version, prior_pending_counts.
    """
    # 1. Fetch report and indicators
    report = ScamReport.objects.prefetch_related("indicators").get(id=report_id)
    indicators = list(report.indicators.all())

    # 2. Fetch active heuristic rules
    rule_rows = HeuristicRule.objects.filter(is_active=True).values("rule_type", "pattern", "weight")
    grouped_rules = {"KEYWORD": [], "TLD": [], "SHORTENER": []}
    for r in rule_rows:
        rtype = r["rule_type"]
        if rtype in grouped_rules:
            grouped_rules[rtype].append({"pattern": r["pattern"], "weight": r["weight"]})

    # 3. Fetch ScannerConfig singleton
    config_obj = (
        ScannerConfig.objects.filter(id=1)
        .values(
            "keyword_cap_points",
            "ip_url_points",
            "prior_pending_points",
            "high_priority_threshold",
            "ruleset_version",
        )
        .first()
    )
    if not config_obj:
        config_obj = {
            "keyword_cap_points": 45,
            "ip_url_points": 25,
            "prior_pending_points": 20,
            "high_priority_threshold": 75,
            "ruleset_version": 1,
        }

    # 4. Compute prior pending counts for this report's indicators across other PENDING reports
    prior_counts = {}
    if indicators:
        q_filter = Q()
        for ind in indicators:
            q_filter |= Q(type=ind.type, normalized_value=ind.normalized_value)

        counts_qs = (
            ReportIndicator.objects.filter(
                q_filter,
                report__status=ReportStatus.PENDING,
            )
            .exclude(report_id=report.id)
            .values("normalized_value")
            .annotate(count=Count("report_id", distinct=True))
        )
        prior_counts = {item["normalized_value"]: item["count"] for item in counts_qs}

    formatted_indicators = [
        {
            "type": ind.type,
            "normalized_value": ind.normalized_value,
            "host": extract_host(ind.type, ind.normalized_value),
        }
        for ind in indicators
    ]

    return {
        "report_id": str(report.id),
        "ruleset_version": config_obj["ruleset_version"],
        "message_text": report.message_text or "",
        "indicators": formatted_indicators,
        "rules": grouped_rules,
        "config": {
            "keyword_cap_points": config_obj["keyword_cap_points"],
            "ip_url_points": config_obj["ip_url_points"],
            "prior_pending_points": config_obj["prior_pending_points"],
            "high_priority_threshold": config_obj["high_priority_threshold"],
        },
        "prior_pending_counts": prior_counts,
    }
