import pytest

from apps.reports.normalizers import (
    NormalizationError,
    normalize_bank_account,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_url,
)


class TestPhoneNormalizer:
    """At least 10 cases covering MY, NP, ZZ, and invalid formats per D56."""

    def test_01_my_mobile_leading_zero(self):
        norm, disp = normalize_phone("0123456789", country_code="MY")
        assert norm == "+60123456789"
        assert "••••" in disp
        assert disp.endswith("6789")

    def test_02_my_mobile_formatted_spaces_dashes(self):
        norm, _ = normalize_phone("012-345 6789", country_code="MY")
        assert norm == "+60123456789"

    def test_03_my_landline(self):
        norm, _ = normalize_phone("03-21234567", country_code="MY")
        assert norm == "+60321234567"

    def test_04_my_already_e164(self):
        norm, _ = normalize_phone("+60123456789", country_code="MY")
        assert norm == "+60123456789"

    def test_05_np_mobile(self):
        norm, disp = normalize_phone("9841234567", country_code="NP")
        assert norm == "+9779841234567"
        assert disp.startswith("+977")

    def test_06_np_landline_with_dash(self):
        norm, _ = normalize_phone("01-4234567", country_code="NP")
        assert norm == "+97714234567"

    def test_07_np_already_e164(self):
        norm, _ = normalize_phone("+9779841234567", country_code="NP")
        assert norm == "+9779841234567"

    def test_08_zz_valid_us_leading_plus(self):
        norm, _ = normalize_phone("+12025550123", country_code="ZZ")
        assert norm == "+12025550123"

    def test_09_zz_valid_uk_leading_plus(self):
        norm, _ = normalize_phone("+447911123456", country_code="ZZ")
        assert norm == "+447911123456"

    def test_10_zz_missing_leading_plus_rejected(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_phone("12025550123", country_code="ZZ")
        assert exc_info.value.code == "missing_international_prefix"

    def test_11_invalid_letters(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_phone("01234abcd", country_code="MY")
        assert exc_info.value.code == "invalid_phone"

    def test_12_invalid_too_short(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_phone("123", country_code="MY")
        assert exc_info.value.code == "invalid_phone"


class TestUrlNormalizer:
    """At least 10 cases covering scheme, host, IDN, query params, length per D56."""

    def test_01_http_basic(self):
        norm, _, domain = normalize_url("http://example.com/login")
        assert norm == "example.com/login"
        assert domain == "example.com"

    def test_02_https_trailing_slash(self):
        norm, _, domain = normalize_url("https://example.com/")
        assert norm == "example.com"
        assert domain == "example.com"

    def test_03_schemeless_input(self):
        norm, _, _ = normalize_url("example.com/phish/verify")
        assert norm == "example.com/phish/verify"

    def test_04_uppercase_host_lowercased_path_preserved(self):
        norm, _, _ = normalize_url("https://PHISHING-PORTAL.COM/LoginCase")
        assert norm == "phishing-portal.com/LoginCase"

    def test_05_default_ports_stripped(self):
        norm80, _, _ = normalize_url("http://example.com:80/path")
        norm443, _, _ = normalize_url("https://example.com:443/path")
        assert norm80 == "example.com/path"
        assert norm443 == "example.com/path"

    def test_06_non_default_port_preserved(self):
        norm, _, _ = normalize_url("http://example.com:8080/portal")
        assert norm == "example.com:8080/portal"

    def test_07_tracking_query_params_dropped(self):
        raw = "https://example.com/page?utm_source=fb&utm_medium=cpc&fbclid=123&gclid=456&keep=important"
        norm, _, _ = normalize_url(raw)
        assert norm == "example.com/page?keep=important"

    def test_08_query_params_sorted(self):
        norm, _, _ = normalize_url("https://example.com/p?b=2&a=1")
        assert norm == "example.com/p?a=1&b=2"

    def test_09_fragment_dropped(self):
        norm, _, _ = normalize_url("https://example.com/login#form-section")
        assert norm == "example.com/login"

    def test_10_idn_punycode(self):
        norm, _, domain = normalize_url("https://münchen.de/portal")
        assert norm.startswith("xn--mnchen-3ya.de/portal")
        assert domain == "xn--mnchen-3ya.de"

    def test_11_disallowed_scheme_rejected(self):
        for bad_url in ["javascript:alert(1)", "ftp://files.com", "data:text/html,abc", "file:///etc/passwd"]:
            with pytest.raises(NormalizationError) as exc_info:
                normalize_url(bad_url)
            assert exc_info.value.code == "disallowed_scheme"

    def test_12_userinfo_rejected(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_url("https://admin:secret@phishing.com/login")
        assert exc_info.value.code == "disallowed_userinfo"

    def test_13_too_long_rejected(self):
        long_url = "https://example.com/" + ("a" * 2040)
        with pytest.raises(NormalizationError) as exc_info:
            normalize_url(long_url)
        assert exc_info.value.code == "url_too_long"

    def test_14_derived_subdomain(self):
        _, _, domain = normalize_url("https://sub.portal.scam-bank.com.my/account")
        assert domain == "scam-bank.com.my"


class TestDomainNormalizer:
    """Domain extraction and normalization cases."""

    def test_01_standard_domain(self):
        norm, _ = normalize_domain("example.com")
        assert norm == "example.com"

    def test_02_subdomain_reduced_to_registrable(self):
        norm, _ = normalize_domain("login.secure.bank.com")
        assert norm == "bank.com"

    def test_03_two_part_tld_uk(self):
        norm, _ = normalize_domain("portal.fraud.co.uk")
        assert norm == "fraud.co.uk"

    def test_04_two_part_tld_my(self):
        norm, _ = normalize_domain("verification.bank.com.my")
        assert norm == "bank.com.my"

    def test_05_two_part_tld_np(self):
        norm, _ = normalize_domain("secure.payment.com.np")
        assert norm == "payment.com.np"

    def test_06_uppercase(self):
        norm, _ = normalize_domain("SUB.EXAMPLE.COM")
        assert norm == "example.com"

    def test_07_full_url_input_as_domain_tolerated(self):
        norm, _ = normalize_domain("https://sub.example.com/path/")
        assert norm == "example.com"

    def test_08_punycode_idn(self):
        norm, _ = normalize_domain("münchen.de")
        assert norm == "xn--mnchen-3ya.de"

    def test_09_invalid_domain_no_suffix(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_domain("localhost")
        assert exc_info.value.code == "invalid_domain"

    def test_10_display_masking(self):
        _, disp = normalize_domain("lazada-promo-scam.xyz")
        assert "••••" in disp
        assert disp.endswith(".xyz")


class TestEmailNormalizer:
    """Email normalization cases."""

    def test_01_standard_email(self):
        norm, _ = normalize_email("User@Example.Com")
        assert norm == "user@example.com"

    def test_02_whitespace_trimmed(self):
        norm, _ = normalize_email("  scammer@fraud.org  ")
        assert norm == "scammer@fraud.org"

    def test_03_plus_addressing_allowed(self):
        norm, _ = normalize_email("victim+alert@domain.com")
        assert norm == "victim+alert@domain.com"

    def test_04_subdomain_email(self):
        norm, _ = normalize_email("support@mail.fake-delivery.com")
        assert norm == "support@mail.fake-delivery.com"

    def test_05_missing_at(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_email("userexample.com")
        assert exc_info.value.code == "invalid_email"

    def test_06_missing_domain(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_email("user@")
        assert exc_info.value.code == "invalid_email"

    def test_07_missing_username(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_email("@example.com")
        assert exc_info.value.code == "invalid_email"

    def test_08_double_at(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_email("user@@example.com")
        assert exc_info.value.code == "invalid_email"

    def test_09_spaces_in_email(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_email("user name@example.com")
        assert exc_info.value.code == "invalid_email"

    def test_10_display_masking(self):
        _, disp = normalize_email("john.doe@scamshield.test")
        assert disp.startswith("j")
        assert "•••" in disp
        assert disp.endswith("@scamshield.test")


class TestBankAccountNormalizer:
    """Bank account normalization, leading zeros, and HMAC requirements per D2, D5, D75."""

    def test_01_clean_digits(self):
        norm, disp = normalize_bank_account("1234567890", hmac_key="test-key-32-chars-long-example!")
        assert len(norm) == 64
        assert disp == "12••••7890"

    def test_02_preserves_leading_zeros(self):
        norm1, _ = normalize_bank_account("0012345678", hmac_key="test-key-32-chars-long-example!")
        norm2, _ = normalize_bank_account("12345678", hmac_key="test-key-32-chars-long-example!")
        assert norm1 != norm2

    def test_03_strips_spaces(self):
        norm1, _ = normalize_bank_account("1234 5678 9012", hmac_key="test-key-32-chars-long-example!")
        norm2, _ = normalize_bank_account("123456789012", hmac_key="test-key-32-chars-long-example!")
        assert norm1 == norm2

    def test_04_strips_dashes(self):
        norm1, _ = normalize_bank_account("123-456-789012", hmac_key="test-key-32-chars-long-example!")
        norm2, _ = normalize_bank_account("123456789012", hmac_key="test-key-32-chars-long-example!")
        assert norm1 == norm2

    def test_05_strips_dots(self):
        norm1, _ = normalize_bank_account("123.456.789.012", hmac_key="test-key-32-chars-long-example!")
        norm2, _ = normalize_bank_account("123456789012", hmac_key="test-key-32-chars-long-example!")
        assert norm1 == norm2

    def test_06_combined_separators(self):
        norm1, _ = normalize_bank_account("  12-34.56 7890  ", hmac_key="test-key-32-chars-long-example!")
        norm2, _ = normalize_bank_account("1234567890", hmac_key="test-key-32-chars-long-example!")
        assert norm1 == norm2

    def test_07_invalid_letters(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_bank_account("1234567ABCD", hmac_key="test-key-32-chars-long-example!")
        assert exc_info.value.code == "invalid_bank_account"

    def test_08_invalid_too_short(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_bank_account("123", hmac_key="test-key-32-chars-long-example!")
        assert exc_info.value.code == "invalid_bank_account"

    def test_09_invalid_empty_or_symbols_only(self):
        with pytest.raises(NormalizationError) as exc_info:
            normalize_bank_account("---...   ", hmac_key="test-key-32-chars-long-example!")
        assert exc_info.value.code == "invalid_bank_account"

    def test_10_deterministic_hmac(self):
        k = "deterministic-key-32-chars-long!"
        n1, _ = normalize_bank_account("9876543210", hmac_key=k)
        n2, _ = normalize_bank_account("9876543210", hmac_key=k)
        assert n1 == n2

    def test_11_key_dependent_hmac(self):
        k1 = "key-one-must-be-32-characters-!!"
        k2 = "key-two-must-be-32-characters-!!"
        n1, _ = normalize_bank_account("9876543210", hmac_key=k1)
        n2, _ = normalize_bank_account("9876543210", hmac_key=k2)
        assert n1 != n2
