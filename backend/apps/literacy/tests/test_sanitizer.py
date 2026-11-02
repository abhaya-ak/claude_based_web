
from apps.literacy.sanitizers import sanitize_markdown


class TestSanitizeMarkdown:
    """
    TO BE PROVEN #17: Stored XSS Neutralization via nh3.
    Verifies that markdown content stored raw in the database is thoroughly
    sanitized on output, eliminating malicious HTML injection vectors while
    preserving legitimate markdown content.
    """

    def test_to_be_proven_17_xss_script_tags_stripped(self):
        malicious = "# Beware of Tax Scams\n<script>alert('pwned');</script>\nAlways check the sender."
        sanitized = sanitize_markdown(malicious)
        assert "<script>" not in sanitized
        assert "alert('pwned')" not in sanitized
        assert "Beware of Tax Scams" in sanitized
        assert "Always check the sender." in sanitized

    def test_to_be_proven_17_xss_onerror_attributes_stripped(self):
        malicious = 'Here is evidence: <img src="invalid-url.png" onerror="alert(document.cookie)">'
        sanitized = sanitize_markdown(malicious)
        assert "onerror" not in sanitized
        assert "document.cookie" not in sanitized

    def test_to_be_proven_17_xss_javascript_urls_stripped(self):
        malicious = '<a href="javascript:alert(1)">Click for refund</a>'
        sanitized = sanitize_markdown(malicious)
        assert "javascript:" not in sanitized
        assert "Click for refund" in sanitized

    def test_to_be_proven_17_iframe_and_style_tags_stripped(self):
        malicious = """
        <iframe src="https://evil-phishing.com/login"></iframe>
        <style>body { display: none; }</style>
        <p>Legitimate paragraph</p>
        """
        sanitized = sanitize_markdown(malicious)
        assert "<iframe" not in sanitized
        assert "<style" not in sanitized
        assert "Legitimate paragraph" in sanitized

    def test_legitimate_markdown_and_html_preserved(self):
        safe_content = (
            "# Recognizing Urgent Phishing\n\n"
            "Scammers use **artificial urgency** to force mistakes.\n\n"
            "Key warning signs:\n"
            "- Demands immediate bank transfer\n"
            "- Claims your account will be suspended\n\n"
            "> Never share your OTP with anyone.\n\n"
            "Official resource: [Bank Negara Malaysia](https://www.bnm.gov.my)"
        )
        sanitized = sanitize_markdown(safe_content)
        assert "# Recognizing Urgent Phishing" in sanitized
        assert "**artificial urgency**" in sanitized
        assert "- Demands immediate bank transfer" in sanitized
        assert "Never share your OTP with anyone." in sanitized
        assert "https://www.bnm.gov.my" in sanitized

    def test_none_and_empty_string_handling(self):
        assert sanitize_markdown("") == ""
        assert sanitize_markdown(None) == ""
