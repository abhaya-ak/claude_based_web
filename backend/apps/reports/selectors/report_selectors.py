import json
from decimal import Decimal
from pathlib import Path

from django.db.models import Case, IntegerField, Q, Value, When

from apps.reports.constants import (
    ALLOWED_COUNTRY_CODES,
    ALLOWED_CURRENCIES,
)
from apps.reports.models import (
    IndicatorType,
    PaymentMethod,
    Platform,
    RecoveryPlaybook,
    ScamCategory,
    ScamReport,
)

BANK_FREEZE_STEP = {
    "marker": "bank_freeze",
    "title": "Emergency bank contact & transaction recall",
    "detail": "Immediately contact your bank's 24/7 fraud hotline to freeze compromised accounts and request an urgent recall of the funds.",
}

DEFAULT_PLAYBOOK = {
    "title": "General Scam Response & Recovery",
    "steps": [
      {
        "marker": "cease_contact",
        "title": "Cease all communication",
        "detail": "Immediately stop all interactions with the suspected scammer. Block phone numbers, messaging accounts, and email addresses.",
      },
      {
        "marker": "secure_accounts",
        "title": "Secure online accounts",
        "detail": "Change passwords on your primary email, banking portals, and social media accounts. Enable multi-factor authentication everywhere.",
      },
      {
        "marker": "preserve_evidence",
        "title": "Preserve incident records",
        "detail": "Take clear screenshots of conversations, transaction receipts, website addresses, and caller numbers before deleting anything.",
      },
      {
        "marker": "report_authorities",
        "title": "Lodge an official report",
        "detail": "File a report with your local police department or national cybercrime agency for official investigation and documentation.",
      },
      {
        "marker": "disclaimer",
        "title": "Important note",
        "detail": "This is general guidance, not legal advice.",
      },
    ],
    "hotlines": [],
}


def get_recovery_playbook(
    category: str | None = None,
    payment_method: str | None = None,
    country_code: str | None = None,
    financial_loss: Decimal | float | int = 0,
) -> dict:
    """
    Finds the best-matching active RecoveryPlaybook per D66 & D78:
    - Candidate match: each field matches or is NULL on playbook (null = any)
    - Ranking: most matching fields wins (3, 2, 1, 0), then highest priority, then lowest id
    - Bank transfer with loss > 0 must contain the bank-freeze step (tested by step marker)
    """
    qs = RecoveryPlaybook.objects.filter(is_active=True)

    # Filter eligible candidates: null matches any
    q_cat = Q(category__isnull=True)
    if category:
        q_cat |= Q(category=category)

    q_pay = Q(payment_method__isnull=True)
    if payment_method:
        q_pay |= Q(payment_method=payment_method)

    q_geo = Q(country_code__isnull=True)
    if country_code:
        q_geo |= Q(country_code=country_code)

    eligible = qs.filter(q_cat & q_pay & q_geo)

    # Score candidates by number of non-null matching fields (0 to 3)
    score_cat = When(category=category, then=Value(1)) if category else When(pk__isnull=False, then=Value(0))
    score_pay = When(payment_method=payment_method, then=Value(1)) if payment_method else When(pk__isnull=False, then=Value(0))
    score_geo = When(country_code=country_code, then=Value(1)) if country_code else When(pk__isnull=False, then=Value(0))

    ranked = eligible.annotate(
        match_score=(
            Case(score_cat, default=Value(0), output_field=IntegerField())
            + Case(score_pay, default=Value(0), output_field=IntegerField())
            + Case(score_geo, default=Value(0), output_field=IntegerField())
        )
    ).order_by("-match_score", "-priority", "id")

    match = ranked.first()

    if match:
        playbook_dict = {
            "title": match.title,
            "steps": [dict(s) for s in match.steps],
            "hotlines": list(match.hotlines),
        }
    else:
        playbook_dict = {
            "title": DEFAULT_PLAYBOOK["title"],
            "steps": [dict(s) for s in DEFAULT_PLAYBOOK["steps"]],
            "hotlines": list(DEFAULT_PLAYBOOK["hotlines"]),
        }

    # D78: Bank transfer with loss > 0 must contain the bank-freeze step
    loss_dec = Decimal(str(financial_loss or 0))
    if payment_method == PaymentMethod.BANK_TRANSFER and loss_dec > Decimal("0.00"):
        has_freeze = any(s.get("marker") == "bank_freeze" for s in playbook_dict["steps"])
        if not has_freeze:
            playbook_dict["steps"].insert(0, BANK_FREEZE_STEP)

    return playbook_dict


def get_report_options() -> dict:
    """
    Returns options and static data for public frontend report filing per D54 & D55.
    """
    data_path = Path(__file__).resolve().parent.parent / "data" / "admin_areas.json"
    admin_areas = {}
    if data_path.exists():
        with open(data_path, encoding="utf-8") as f:
            admin_areas = json.load(f)

    countries = [
        {"code": "MY", "name": "Malaysia"},
        {"code": "NP", "name": "Nepal"},
        {"code": "ZZ", "name": "Other / International"},
    ]

    return {
        "countries": [c for c in countries if c["code"] in ALLOWED_COUNTRY_CODES],
        "currencies": sorted(list(ALLOWED_CURRENCIES)),
        "categories": [{"code": c[0], "label": c[1]} for c in ScamCategory.choices],
        "platforms": [{"code": p[0], "label": p[1]} for p in Platform.choices],
        "payment_methods": [{"code": m[0], "label": m[1]} for m in PaymentMethod.choices],
        "indicator_types": [{"code": t[0], "label": t[1]} for t in IndicatorType.choices],
        "admin_areas": admin_areas,
    }


def get_report_by_reference(reference_code: str) -> ScamReport | None:
    """Retrieves a report by reference code."""
    return ScamReport.objects.filter(reference_code=reference_code).first()
