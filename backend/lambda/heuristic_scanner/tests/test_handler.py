import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from handler import lambda_handler


class DummyContext:
    aws_request_id = "test-lambda-req-id-123"


def test_lambda_handler_posts_signed_result(monkeypatch):
    secret = "test-secret-at-least-32-chars-long-for-hmac"
    monkeypatch.setenv("SCANNER_CALLBACK_SECRET", secret)
    monkeypatch.setenv("SCANNER_CALLBACK_URL", "http://localhost:8000/api/v1/internal/scan-results/")

    event = {
        "report_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "ruleset_version": 2,
        "message_text": "Urgent bank alert",
        "indicators": [{"type": "URL", "host": "bit.ly"}],
        "rules": {
            "KEYWORD": [{"pattern": "urgent", "weight": 15}],
            "TLD": [],
            "SHORTENER": [{"pattern": "bit.ly", "weight": 15}],
        },
        "config": {
            "keyword_cap_points": 45,
            "ip_url_points": 25,
            "prior_pending_points": 20,
            "high_priority_threshold": 75,
        },
        "prior_pending_counts": {},
    }

    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = b'{"status": "success"}'
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        res = lambda_handler(event, DummyContext())

        assert res["statusCode"] == 200
        data = json.loads(res["body"])
        assert data["report_id"] == event["report_id"]
        assert data["ruleset_version"] == 2
        assert data["risk_score"] == 30
        assert data["lambda_request_id"] == "test-lambda-req-id-123"

        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://localhost:8000/api/v1/internal/scan-results/"
        assert req.headers["Content-type"] == "application/json"

        # Verify HMAC signature
        ts = req.headers["X-timestamp"]
        sig = req.headers["X-signature"]
        body = req.data
        expected_sig = hmac.new(
            secret.encode(),
            f"{ts}.".encode() + body,
            hashlib.sha256,
        ).hexdigest()
        assert hmac.compare_digest(sig, expected_sig)
