import hashlib
import hmac
import re
import urllib.parse

import phonenumbers
import tldextract
from django.conf import settings

from apps.reports.constants import MAX_URL_LENGTH

# Tracking query parameters to strip per D56
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "igshid",
    "_ga",
    "mc_cid",
    "mc_eid",
}

# Offline tldextract instance per D72 (zero network, zero disk writes)
_tld_extractor = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class NormalizationError(Exception):
    """Raised when an indicator fails pure normalization per D74."""

    def __init__(self, field: str, code: str, message: str = ""):
        self.field = field
        self.code = code
        self.message = message or f"Invalid {field} format."
        super().__init__(self.message)


def normalize_phone(raw_phone: str, country_code: str = "MY") -> tuple[str, str]:
    """
    Normalises phone number to E.164 using country_code as default region.
    ZZ requires a leading '+' per D55.
    Returns (normalized_e164, display_masked).
    """
    raw = (raw_phone or "").strip()
    cc = (country_code or "MY").strip().upper()

    if not raw:
        raise NormalizationError("phone", "invalid_phone", "Phone number cannot be empty.")

    if cc == "ZZ":
        if not raw.startswith("+"):
            raise NormalizationError(
                "phone",
                "missing_international_prefix",
                "International numbers with other country code require leading +.",
            )

    try:
        parsed = phonenumbers.parse(raw, cc if cc != "ZZ" else None)
    except Exception as e:
        raise NormalizationError("phone", "invalid_phone", "Could not parse phone number.") from e

    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        raise NormalizationError("phone", "invalid_phone", "Invalid or impossible phone number.")

    normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    # Mask middle digits for display: keep +country_code + first digit, mask middle, keep last 4
    if len(normalized) > 7:
        prefix_len = len(str(parsed.country_code)) + 2  # e.g., +601
        display = normalized[:prefix_len] + "•••••" + normalized[-4:]
    else:
        display = normalized[:2] + "•••" + normalized[-2:]

    return normalized, display


def normalize_url(raw_url: str) -> tuple[str, str, str | None]:
    """
    Normalises URL to scheme-less canonical form per D56.
    Rejects non-http(s) schemes, userinfo, and URLs > 2048 chars.
    Auto-derives registrable domain via offline tldextract.
    Returns (canonical_url, display_masked, derived_domain).
    """
    raw = (raw_url or "").strip()
    if not raw:
        raise NormalizationError("url", "invalid_url", "URL cannot be empty.")

    if len(raw) > MAX_URL_LENGTH:
        raise NormalizationError("url", "url_too_long", f"URL exceeds maximum length of {MAX_URL_LENGTH} characters.")

    # Check scheme: e.g. "http://", "https://", or disallowed schemes like "javascript:", "ftp:", "data:"
    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", raw)
    if scheme_match:
        scheme_found = scheme_match.group(1).lower()
        if scheme_found not in ("http", "https"):
            raise NormalizationError("url", "disallowed_scheme", f"Scheme '{scheme_found}' is not allowed.")
        if not raw.startswith(f"{scheme_found}://"):
            # e.g. "http:example.com" without "//"
            raw = f"{scheme_found}://" + raw[len(scheme_found) + 1:].lstrip("/")
    else:
        # Prepend scheme for parser
        raw = "https://" + raw

    try:
        parsed = urllib.parse.urlsplit(raw)
        host = parsed.hostname
        port = parsed.port
    except ValueError as e:
        raise NormalizationError("url", "invalid_url", "Malformed URL or port.") from e
    except Exception as e:
        raise NormalizationError("url", "invalid_url", "Malformed URL.") from e

    if parsed.username or parsed.password:
        raise NormalizationError("url", "disallowed_userinfo", "URLs containing userinfo are disallowed.")

    if not host:
        raise NormalizationError("url", "invalid_url", "URL missing valid host.")

    # Punycode / IDN encoding and lowercase host
    try:
        host = host.encode("idna").decode("ascii").lower()
    except Exception as e:
        raise NormalizationError("url", "invalid_url", "Invalid internationalized domain in URL.") from e

    # Default port removal
    if port:
        if (parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443):
            netloc = host
        else:
            netloc = f"{host}:{port}"
    else:
        netloc = host

    # Path normalization: strip trailing slash
    path = parsed.path or ""
    if path == "/":
        path = ""
    elif path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")

    # Query params: strip tracking params and sort remaining
    clean_params = []
    if parsed.query:
        for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
            if k.lower() not in TRACKING_PARAMS:
                clean_params.append((k, v))
        clean_params.sort(key=lambda x: (x[0], x[1]))

    query_str = urllib.parse.urlencode(clean_params, doseq=True) if clean_params else ""

    canonical = f"{netloc}{path}" + (f"?{query_str}" if query_str else "")

    # Derive domain offline via tldextract
    ext = _tld_extractor(host)
    reg_domain = ext.top_domain_under_public_suffix
    derived_domain = reg_domain.lower() if reg_domain else None

    # Masked display
    parts = host.split(".")
    if len(parts) >= 2 and len(parts[0]) > 3:
        masked_host = parts[0][:3] + "••••." + ".".join(parts[1:])
    else:
        masked_host = host
    display = f"{masked_host}{path}" + (f"?{query_str}" if query_str else "")

    return canonical, display, derived_domain


def normalize_domain(raw_domain: str) -> tuple[str, str]:
    """
    Normalises domain string to registrable lower-case domain via offline tldextract.
    Returns (normalized_domain, display_masked).
    """
    raw = (raw_domain or "").strip()
    if not raw:
        raise NormalizationError("domain", "invalid_domain", "Domain cannot be empty.")

    # Strip scheme or path if user pasted full URL
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    if "/" in raw:
        raw = raw.split("/", 1)[0]
    if ":" in raw:
        raw = raw.split(":", 1)[0]

    # Punycode / IDN
    try:
        host = raw.encode("idna").decode("ascii").lower()
    except Exception as e:
        raise NormalizationError("domain", "invalid_domain", "Invalid domain encoding.") from e

    ext = _tld_extractor(host)
    reg_domain = ext.top_domain_under_public_suffix
    if not reg_domain or not ext.suffix:
        raise NormalizationError("domain", "invalid_domain", "Must be a valid registrable domain with a known suffix.")

    normalized = reg_domain.lower()

    # Mask display
    name_parts = normalized.split(".")
    main_name = name_parts[0]
    suffix = ".".join(name_parts[1:])
    if len(main_name) > 4:
        display = f"{main_name[:4]}••••.{suffix}"
    else:
        display = f"{main_name}••••.{suffix}"

    return normalized, display


def normalize_email(raw_email: str) -> tuple[str, str]:
    """
    Normalises email to trimmed, lower-case format.
    Returns (normalized_email, display_masked).
    """
    raw = (raw_email or "").strip().lower()
    if not raw or not EMAIL_REGEX.match(raw) or ".." in raw or raw.startswith("@") or raw.endswith("@"):
        raise NormalizationError("email", "invalid_email", "Invalid email address format.")

    user, domain = raw.split("@", 1)
    if not user or not domain:
        raise NormalizationError("email", "invalid_email", "Invalid email address format.")

    display = f"{user[0]}•••@{domain}"
    return raw, display


def normalize_bank_account(raw_account: str, hmac_key: str | None = None) -> tuple[str, str]:
    """
    Normalises bank account: strips spaces, dashes, dots; retains leading zeros;
    computes HMAC-SHA256 hex digest using INDICATOR_HMAC_KEY per D2, D5, D75.
    Returns (normalized_hmac_hex, display_masked).
    """
    raw = (raw_account or "").strip()
    if not raw:
        raise NormalizationError("bank_account", "invalid_bank_account", "Bank account cannot be empty.")

    clean_digits = re.sub(r"[\s\-\.]+", "", raw)
    if not clean_digits.isdigit():
        raise NormalizationError("bank_account", "invalid_bank_account", "Bank account must contain digits only.")

    if len(clean_digits) < 5 or len(clean_digits) > 30:
        raise NormalizationError(
            "bank_account", "invalid_bank_account", "Bank account length must be between 5 and 30 digits."
        )

    key = hmac_key or getattr(settings, "INDICATOR_HMAC_KEY", "")
    if not key:
        raise ValueError("INDICATOR_HMAC_KEY is required for bank account hashing.")

    normalized_hmac = hmac.new(key.encode("utf-8"), clean_digits.encode("utf-8"), hashlib.sha256).hexdigest()

    if len(clean_digits) >= 6:
        display = f"{clean_digits[:2]}••••{clean_digits[-4:]}"
    else:
        display = f"••••{clean_digits[-2:]}"

    return normalized_hmac, display
