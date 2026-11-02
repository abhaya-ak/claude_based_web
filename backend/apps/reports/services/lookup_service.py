import logging
from typing import Any

from apps.intel.models import ThreatLevel
from apps.intel.selectors.intel_selectors import (
    count_pending_by_indicator,
    find_active_indicators,
)
from apps.reports.services.lookup_detector import detect_candidate_pairs

logger = logging.getLogger(__name__)

THREAT_RANK: dict[str, int] = {
    ThreatLevel.CRITICAL: 3,
    ThreatLevel.HIGH: 2,
    ThreatLevel.MEDIUM: 1,
}


def determine_verdict(query: str | None) -> dict[str, Any]:
    """
    Evaluates candidate indicators against active VerifiedIndicators and pending reports
    per D102 and Phase 7 specifications.

    Verdict hierarchy:
    - RED: Active VerifiedIndicator matches any candidate pair.
           Selects indicator with highest threat level.
    - YELLOW: No active VI, but pending report count >= 1.
    - GREEN: No active VI and 0 pending reports (or invalid/conversational query).

    R-C5: Never log raw query string.
    R-C8: Response contains only public non-PII fields.
    """
    candidate_pairs = detect_candidate_pairs(query)
    str_pairs = [
        (p[0].value if hasattr(p[0], "value") else str(p[0]), p[1])
        for p in candidate_pairs
    ]

    if not str_pairs:
        return {
            "verdict": "GREEN",
            "threat_level": None,
            "category": None,
            "report_count": 0,
            "first_seen_at": None,
            "last_seen_at": None,
            "public_note": None,
            "message": "No scam reports found matching this indicator. Always stay alert and verify through trusted official channels.",
        }

    # 1. Search active verified indicators (Contract §3.6)
    active_indicators = list(find_active_indicators(str_pairs))
    if active_indicators:
        best_vi = max(
            active_indicators,
            key=lambda vi: (
                THREAT_RANK.get(vi.threat_level, 0),
                vi.total_report_count or 0,
            ),
        )
        return {
            "verdict": "RED",
            "threat_level": best_vi.threat_level,
            "category": best_vi.primary_category,
            "report_count": best_vi.total_report_count,
            "first_seen_at": best_vi.first_seen_at,
            "last_seen_at": best_vi.last_seen_at,
            "public_note": best_vi.public_note or None,
            "message": "This indicator matches a verified scam threat in our database. Do not engage or send money/information.",
        }

    # 2. Check pending reports count (Contract §3.6)
    pending_counts = count_pending_by_indicator(str_pairs)
    total_pending = sum(pending_counts.values())
    if total_pending > 0:
        return {
            "verdict": "YELLOW",
            "threat_level": None,
            "category": None,
            "report_count": total_pending,
            "first_seen_at": None,
            "last_seen_at": None,
            "public_note": None,
            "message": "This indicator has been reported and is awaiting verification by analysts. Exercise caution.",
        }

    # 3. Clean indicator
    return {
        "verdict": "GREEN",
        "threat_level": None,
        "category": None,
        "report_count": 0,
        "first_seen_at": None,
        "last_seen_at": None,
        "public_note": None,
        "message": "No scam reports found matching this indicator. Always stay alert and verify through trusted official channels.",
    }
