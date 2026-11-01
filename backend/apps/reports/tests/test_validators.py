from decimal import Decimal

import pytest

from apps.reports.normalizers import NormalizationError
from apps.reports.validators import (
    validate_admin_area,
    validate_country_code,
    validate_currency,
    validate_financial_loss,
    validate_indicator_counts,
    validate_message_text,
)


class TestValidators:
    """Validation rules per D55 and D57."""

    def test_country_code_valid(self):
        assert validate_country_code("MY") == "MY"
        assert validate_country_code("np") == "NP"
        assert validate_country_code("ZZ") == "ZZ"

    def test_country_code_invalid(self):
        for bad in ["US", "GB", "SG", "XX", ""]:
            with pytest.raises(NormalizationError) as exc_info:
                validate_country_code(bad)
            assert exc_info.value.code == "invalid_country"

    def test_currency_valid(self):
        assert validate_currency("MYR") == "MYR"
        assert validate_currency("npr") == "NPR"
        assert validate_currency("USD") == "USD"

    def test_currency_invalid(self):
        for bad in ["EUR", "GBP", "SGD", ""]:
            with pytest.raises(NormalizationError) as exc_info:
                validate_currency(bad)
            assert exc_info.value.code == "invalid_currency"

    def test_admin_area_my(self):
        assert validate_admin_area("MY", "Selangor") == "Selangor"
        assert validate_admin_area("MY", "Wilayah Persekutuan Kuala Lumpur") == "Wilayah Persekutuan Kuala Lumpur"
        assert validate_admin_area("MY", None) is None
        with pytest.raises(NormalizationError) as exc_info:
            validate_admin_area("MY", "California")
        assert exc_info.value.code == "invalid_admin_area"

    def test_admin_area_np(self):
        assert validate_admin_area("NP", "Bagmati Province") == "Bagmati Province"
        with pytest.raises(NormalizationError) as exc_info:
            validate_admin_area("NP", "Selangor")
        assert exc_info.value.code == "invalid_admin_area"

    def test_admin_area_zz(self):
        assert validate_admin_area("ZZ", None) is None
        assert validate_admin_area("ZZ", "") is None
        with pytest.raises(NormalizationError) as exc_info:
            validate_admin_area("ZZ", "Any Area")
        assert exc_info.value.code == "invalid_admin_area"

    def test_message_text_valid(self):
        assert validate_message_text("Hello scam") == "Hello scam"
        assert validate_message_text("  trimmed  ") == "trimmed"
        # Control characters stripped but newlines kept
        text_with_control = "Line 1\x00\x08\r\nLine 2\x1f\tDone"
        cleaned = validate_message_text(text_with_control)
        assert "\x00" not in cleaned
        assert "\x08" not in cleaned
        assert "\x1f" not in cleaned
        assert "Line 1\r\nLine 2\tDone" == cleaned

    def test_message_text_limits(self):
        with pytest.raises(NormalizationError) as exc_info:
            validate_message_text("")
        assert exc_info.value.code == "invalid_message_length"

        with pytest.raises(NormalizationError) as exc_info:
            validate_message_text("   \t\n   ")
        assert exc_info.value.code == "invalid_message_length"

        with pytest.raises(NormalizationError) as exc_info:
            validate_message_text("a" * 5001)
        assert exc_info.value.code == "invalid_message_length"

        assert len(validate_message_text("a" * 5000)) == 5000

    def test_financial_loss_valid(self):
        assert validate_financial_loss(0, "NONE") == Decimal("0.00")
        assert validate_financial_loss("150.50", "BANK_TRANSFER") == Decimal("150.50")
        assert validate_financial_loss(Decimal("9999999999.99"), "CRYPTO") == Decimal("9999999999.99")

    def test_financial_loss_negative_rejected(self):
        with pytest.raises(NormalizationError) as exc_info:
            validate_financial_loss("-10.00", "CARD")
        assert exc_info.value.code == "invalid_financial_loss"

    def test_financial_loss_too_large_rejected(self):
        with pytest.raises(NormalizationError) as exc_info:
            validate_financial_loss("10000000000.00", "CARD")
        assert exc_info.value.code == "invalid_financial_loss"

    def test_financial_loss_none_method_with_loss_rejected(self):
        with pytest.raises(NormalizationError) as exc_info:
            validate_financial_loss("50.00", "NONE")
        assert exc_info.value.code == "invalid_loss_for_payment_method"

    def test_indicator_counts(self):
        validate_indicator_counts(submitted_count=1, total_count=1)
        validate_indicator_counts(submitted_count=5, total_count=10)

        with pytest.raises(NormalizationError) as exc_info:
            validate_indicator_counts(submitted_count=0, total_count=0)
        assert exc_info.value.code == "invalid_indicator_count"

        with pytest.raises(NormalizationError) as exc_info:
            validate_indicator_counts(submitted_count=6, total_count=6)
        assert exc_info.value.code == "invalid_indicator_count"

        with pytest.raises(NormalizationError) as exc_info:
            validate_indicator_counts(submitted_count=5, total_count=11)
        assert exc_info.value.code == "total_indicator_limit_exceeded"
