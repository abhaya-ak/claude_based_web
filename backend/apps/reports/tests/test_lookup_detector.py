from apps.intel.models import IndicatorType
from apps.reports.normalizers import normalize_bank_account
from apps.reports.services.lookup_detector import detect_candidate_pairs


class TestLookupDetector:
    def test_empty_or_whitespace_returns_empty_list(self):
        assert detect_candidate_pairs("") == []
        assert detect_candidate_pairs("   ") == []
        assert detect_candidate_pairs(None) == []

    def test_conversational_text_returns_empty_list(self):
        assert detect_candidate_pairs("hello world") == []
        assert detect_candidate_pairs("can you check this scam please?") == []

    def test_email_detection(self):
        pairs = detect_candidate_pairs("Victim@ScamMail.com")
        assert (IndicatorType.EMAIL, "victim@scammail.com") in pairs

    def test_url_detection_emits_both_url_and_domain(self):
        query = "https://login.evil-phish.xyz/secure/login.php?ref=123"
        pairs = detect_candidate_pairs(query)
        types = [t for t, _ in pairs]
        assert IndicatorType.URL in types
        assert IndicatorType.DOMAIN in types

        # Check canonical form and domain
        canon_url = next(val for t, val in pairs if t == IndicatorType.URL)
        domain = next(val for t, val in pairs if t == IndicatorType.DOMAIN)
        assert canon_url == "login.evil-phish.xyz/secure/login.php?ref=123"
        assert domain == "evil-phish.xyz"

    def test_bare_domain_detection(self):
        pairs = detect_candidate_pairs("evil-phish.xyz")
        types = [t for t, _ in pairs]
        assert IndicatorType.DOMAIN in types
        domain = next(val for t, val in pairs if t == IndicatorType.DOMAIN)
        assert domain == "evil-phish.xyz"

    def test_my_local_phone_detection(self):
        pairs = detect_candidate_pairs("012-3456789")
        phone_matches = [val for t, val in pairs if t == IndicatorType.PHONE]
        assert "+60123456789" in phone_matches

    def test_international_phone_detection(self):
        pairs = detect_candidate_pairs("+65 6123 4567")
        phone_matches = [val for t, val in pairs if t == IndicatorType.PHONE]
        assert "+6561234567" in phone_matches

    def test_numeric_query_matches_both_phone_and_bank_account(self):
        # 10 digits can be both a Malaysian mobile phone and a bank account
        raw = "0123456789"
        pairs = detect_candidate_pairs(raw)
        types = [t for t, _ in pairs]
        assert IndicatorType.PHONE in types
        assert IndicatorType.BANK_ACCOUNT in types

        expected_phone = "+60123456789"
        expected_bank_hmac, _ = normalize_bank_account(raw)
        assert (IndicatorType.PHONE, expected_phone) in pairs
        assert (IndicatorType.BANK_ACCOUNT, expected_bank_hmac) in pairs

    def test_bank_account_digits_only(self):
        # 16-digit account number (impossible phone)
        raw = "1234-5678-9012-3456"
        pairs = detect_candidate_pairs(raw)
        types = [t for t, _ in pairs]
        assert IndicatorType.BANK_ACCOUNT in types
        expected_bank_hmac, _ = normalize_bank_account(raw)
        assert (IndicatorType.BANK_ACCOUNT, expected_bank_hmac) in pairs

    def test_deduplication_preserves_order(self):
        pairs = detect_candidate_pairs("evil-domain.com")
        # Ensure no duplicate tuples
        assert len(pairs) == len(set(pairs))
