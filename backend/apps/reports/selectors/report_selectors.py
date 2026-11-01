from apps.reports.models import RecoveryPlaybook, ScamReport

DEFAULT_PLAYBOOK = {
    "title": "General Scam Recovery Guidance",
    "steps": [
        "Cease all contact with the suspected scammer immediately.",
        "Do not send additional funds, passwords, or personal credentials.",
        "Preserve evidence including messages, phone numbers, and receipts.",
        "Contact your bank or financial institution if money was transferred.",
        "File an official report with local authorities or law enforcement.",
    ],
    "hotlines": [],
}


def get_recovery_playbook(
    category: str | None = None,
    payment_method: str | None = None,
    country_code: str | None = None,
) -> dict:
    """
    Finds the best-matching active RecoveryPlaybook based on category, payment method,
    and country, ordered by priority descending per D76.
    Returns a dict with title, steps, hotlines.
    """
    qs = RecoveryPlaybook.objects.filter(is_active=True)

    # 1. Exact match on all three
    if category and payment_method and country_code:
        match = qs.filter(
            category=category,
            payment_method=payment_method,
            country_code=country_code,
        ).order_by("-priority").first()
        if match:
            return {"title": match.title, "steps": match.steps, "hotlines": match.hotlines}

    # 2. Match on category and payment_method
    if category and payment_method:
        match = qs.filter(
            category=category,
            payment_method=payment_method,
        ).order_by("-priority").first()
        if match:
            return {"title": match.title, "steps": match.steps, "hotlines": match.hotlines}

    # 3. Match on category alone
    if category:
        match = qs.filter(category=category).order_by("-priority").first()
        if match:
            return {"title": match.title, "steps": match.steps, "hotlines": match.hotlines}

    # 4. Highest priority generic active playbook
    generic = qs.order_by("-priority").first()
    if generic:
        return {"title": generic.title, "steps": generic.steps, "hotlines": generic.hotlines}

    return DEFAULT_PLAYBOOK


def get_report_by_reference(reference_code: str) -> ScamReport | None:
    """Retrieves a report by reference code."""
    return ScamReport.objects.filter(reference_code=reference_code).first()
