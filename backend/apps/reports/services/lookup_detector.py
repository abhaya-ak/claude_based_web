import re

from apps.intel.models import IndicatorType
from apps.reports.normalizers import (
    NormalizationError,
    normalize_bank_account,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_url,
)


def detect_candidate_pairs(query: str | None) -> list[tuple[IndicatorType, str]]:
    """
    Auto-detects and normalizes potential scam indicator candidate pairs
    (IndicatorType, normalized_value) from a raw lookup query string per D101.

    Detection order:
    1. EMAIL: if contains '@' and passes normalize_email
    2. URL: if contains '://' or '/' or '?' and passes normalize_url (emits URL and DOMAIN)
    3. DOMAIN: if passes normalize_domain
    4. PHONE: if passes normalize_phone (country_code='ZZ' if starts with '+', else 'MY')
    5. BANK_ACCOUNT: if stripped digits are 5..30 chars, passes normalize_bank_account
    (Numeric strings can match both PHONE and BANK_ACCOUNT)
    6. Deduplicate candidates preserving emitted order.
    """
    if not query or not isinstance(query, str):
        return []

    raw = query.strip()
    if not raw or len(raw) > 255:
        return []

    candidates: list[tuple[IndicatorType, str]] = []

    # 1. Email check
    if "@" in raw:
        try:
            norm_email, _ = normalize_email(raw)
            candidates.append((IndicatorType.EMAIL, norm_email))
        except NormalizationError:
            pass

    # 2. URL check (no whitespace, must have scheme or host with path)
    if " " not in raw and ("://" in raw or ("/" in raw and not raw.startswith("/") and "." in raw.split("/", 1)[0])):
        try:
            canon_url, _, derived_domain = normalize_url(raw)
            candidates.append((IndicatorType.URL, canon_url))
            if derived_domain:
                candidates.append((IndicatorType.DOMAIN, derived_domain))
        except NormalizationError:
            pass

    # 3. Domain check
    try:
        norm_domain, _ = normalize_domain(raw)
        candidates.append((IndicatorType.DOMAIN, norm_domain))
    except NormalizationError:
        pass

    # 4. Phone check
    if any(char.isdigit() for char in raw):
        cc = "ZZ" if raw.startswith("+") else "MY"
        try:
            norm_phone, _ = normalize_phone(raw, country_code=cc)
            candidates.append((IndicatorType.PHONE, norm_phone))
        except NormalizationError:
            pass

    # 5. Bank account check (digits with optional spaces, dashes, dots)
    clean_digits = re.sub(r"[\s\-\.]+", "", raw)
    if clean_digits.isdigit() and 5 <= len(clean_digits) <= 30:
        try:
            norm_bank_hmac, _ = normalize_bank_account(raw)
            candidates.append((IndicatorType.BANK_ACCOUNT, norm_bank_hmac))
        except (NormalizationError, ValueError):
            pass

    # 6. Deduplicate preserving order
    unique_pairs: list[tuple[IndicatorType, str]] = []
    seen = set()
    for pair in candidates:
        if pair not in seen:
            seen.add(pair)
            unique_pairs.append(pair)

    return unique_pairs
