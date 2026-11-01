import json
import os
import re
from decimal import Decimal, InvalidOperation

from apps.reports.constants import (
    ALLOWED_COUNTRY_CODES,
    ALLOWED_CURRENCIES,
    MAX_FINANCIAL_LOSS,
    MAX_MESSAGE_LENGTH,
    MAX_SUBMITTED_INDICATORS,
    MAX_TOTAL_INDICATORS,
    MIN_FINANCIAL_LOSS,
    MIN_MESSAGE_LENGTH,
    MIN_SUBMITTED_INDICATORS,
)
from apps.reports.normalizers import NormalizationError

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_ADMIN_AREAS_FILE = os.path.join(_DATA_DIR, "admin_areas.json")

# Load static admin areas map per D55
with open(_ADMIN_AREAS_FILE, encoding="utf-8") as f:
    _ADMIN_AREAS = json.load(f)

# Regex matching non-printable control characters except \t, \n, \r
_CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def validate_country_code(country_code: str) -> str:
    """Validates country code against allowed MY, NP, ZZ per D55."""
    code = (country_code or "").strip().upper()
    if code not in ALLOWED_COUNTRY_CODES:
        raise NormalizationError(
            "country_code",
            "invalid_country",
            f"Country code '{code}' is not supported. Allowed: {sorted(ALLOWED_COUNTRY_CODES)}.",
        )
    return code


def validate_currency(currency: str) -> str:
    """Validates currency against allowed MYR, NPR, USD per D55."""
    curr = (currency or "").strip().upper()
    if curr not in ALLOWED_CURRENCIES:
        raise NormalizationError(
            "currency",
            "invalid_currency",
            f"Currency '{curr}' is not supported. Allowed: {sorted(ALLOWED_CURRENCIES)}.",
        )
    return curr


def validate_admin_area(country_code: str, admin_area: str | None) -> str | None:
    """Validates admin_area against static allow-list per country per D55."""
    cc = validate_country_code(country_code)
    area = (admin_area or "").strip()

    if cc == "ZZ":
        if area:
            raise NormalizationError(
                "admin_area",
                "invalid_admin_area",
                "Admin area must be empty when country code is 'ZZ'.",
            )
        return None

    if not area:
        return None

    allowed = _ADMIN_AREAS.get(cc, [])
    # Case-insensitive lookup preserving canonical title
    matched = next((item for item in allowed if item.lower() == area.lower()), None)
    if not matched:
        raise NormalizationError(
            "admin_area",
            "invalid_admin_area",
            f"Admin area '{area}' is not a recognized state/province for country '{cc}'.",
        )
    return matched


def validate_message_text(text: str) -> str:
    """
    Validates message_text length (1..5000 chars) after trimming and stripping
    control characters per D57.
    """
    raw = (text or "").strip()
    cleaned = _CONTROL_CHAR_REGEX.sub("", raw).strip()

    if len(cleaned) < MIN_MESSAGE_LENGTH or len(cleaned) > MAX_MESSAGE_LENGTH:
        raise NormalizationError(
            "message_text",
            "invalid_message_length",
            f"Message text must be between {MIN_MESSAGE_LENGTH} and {MAX_MESSAGE_LENGTH} characters.",
        )
    return cleaned


def validate_financial_loss(loss: Decimal | int | float | str, payment_method: str) -> Decimal:
    """
    Validates financial_loss within 0..9999999999.99.
    If payment_method is NONE, loss must be 0 per D57.
    """
    try:
        dec_loss = Decimal(str(loss)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as e:
        raise NormalizationError("financial_loss", "invalid_financial_loss", "Financial loss must be a valid number.") from e

    if dec_loss < MIN_FINANCIAL_LOSS or dec_loss > MAX_FINANCIAL_LOSS:
        raise NormalizationError(
            "financial_loss",
            "invalid_financial_loss",
            f"Financial loss must be between {MIN_FINANCIAL_LOSS} and {MAX_FINANCIAL_LOSS}.",
        )

    pm = (payment_method or "NONE").strip().upper()
    if pm == "NONE" and dec_loss > Decimal("0.00"):
        raise NormalizationError(
            "financial_loss",
            "invalid_loss_for_payment_method",
            "Financial loss must be 0.00 when payment method is NONE.",
        )

    return dec_loss


def validate_indicator_counts(submitted_count: int, total_count: int) -> None:
    """
    Validates indicator counts:
    1..5 submitted indicators (user-provided).
    <= 10 total indicators including auto-derived DOMAIN rows per D1 & D57.
    """
    if submitted_count < MIN_SUBMITTED_INDICATORS or submitted_count > MAX_SUBMITTED_INDICATORS:
        raise NormalizationError(
            "indicators",
            "invalid_indicator_count",
            f"Submitted indicators must be between {MIN_SUBMITTED_INDICATORS} and {MAX_SUBMITTED_INDICATORS}.",
        )

    if total_count > MAX_TOTAL_INDICATORS:
        raise NormalizationError(
            "indicators",
            "total_indicator_limit_exceeded",
            f"Total indicators cannot exceed {MAX_TOTAL_INDICATORS} rows.",
        )
