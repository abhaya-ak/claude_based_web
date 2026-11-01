import pytest
from scoring import score_report


@pytest.fixture
def default_config():
    return {
        "keyword_cap_points": 45,
        "ip_url_points": 25,
        "prior_pending_points": 20,
        "high_priority_threshold": 75,
    }


@pytest.fixture
def base_payload(default_config):
    return {
        "report_id": "11111111-2222-3333-4444-555555555555",
        "ruleset_version": 1,
        "message_text": "",
        "indicators": [],
        "rules": {
            "KEYWORD": [],
            "TLD": [],
            "SHORTENER": [],
        },
        "config": default_config,
        "prior_pending_counts": {},
    }


def test_no_matches_returns_zero(base_payload):
    result = score_report(base_payload)
    assert result["risk_score"] == 0
    assert result["is_high_priority"] is False
    assert result["breakdown"] == []


def test_keyword_single_match(base_payload):
    base_payload["message_text"] = "Please send your OTP immediately"
    base_payload["rules"]["KEYWORD"] = [{"pattern": "otp", "weight": 15}]
    result = score_report(base_payload)
    assert result["risk_score"] == 15
    assert result["is_high_priority"] is False
    assert len(result["breakdown"]) == 1
    assert result["breakdown"][0]["rule"] == "otp"
    assert result["breakdown"][0]["type"] == "KEYWORD"
    assert result["breakdown"][0]["points"] == 15


def test_keyword_whole_word_boundary(base_payload):
    # 'otp' must not match 'hotpot'
    base_payload["message_text"] = "Having hotpot for dinner tonight"
    base_payload["rules"]["KEYWORD"] = [{"pattern": "otp", "weight": 15}]
    result = score_report(base_payload)
    assert result["risk_score"] == 0

    # 'otp' matches 'your otp!'
    base_payload["message_text"] = "Your OTP! Do not share"
    result2 = score_report(base_payload)
    assert result2["risk_score"] == 15


def test_keyword_cap_at_configured_value(base_payload):
    # 4 keywords * 15 = 60, cap is 45
    base_payload["message_text"] = "urgent bank police arrest"
    base_payload["rules"]["KEYWORD"] = [
        {"pattern": "urgent", "weight": 15},
        {"pattern": "bank", "weight": 15},
        {"pattern": "police", "weight": 15},
        {"pattern": "arrest", "weight": 15},
    ]
    result = score_report(base_payload)
    assert result["risk_score"] == 45
    assert result["is_high_priority"] is False


def test_tld_max_weight(base_payload):
    base_payload["indicators"] = [
        {"type": "URL", "host": "phishing.xyz"},
        {"type": "DOMAIN", "host": "malicious.top"},
    ]
    base_payload["rules"]["TLD"] = [
        {"pattern": ".xyz", "weight": 20},
        {"pattern": ".top", "weight": 35},
    ]
    result = score_report(base_payload)
    assert result["risk_score"] == 35


def test_ip_based_url_ipv4_and_ipv6(base_payload):
    # IPv4
    base_payload["indicators"] = [{"type": "URL", "host": "192.168.1.1"}]
    result = score_report(base_payload)
    assert result["risk_score"] == 25

    # IPv6 (strip brackets)
    base_payload["indicators"] = [{"type": "URL", "host": "[2001:db8::1]"}]
    result6 = score_report(base_payload)
    assert result6["risk_score"] == 25


def test_max_tld_and_ip_url(base_payload):
    # TLD 30 > IP 25 -> 30
    base_payload["indicators"] = [
        {"type": "URL", "host": "192.168.1.1"},
        {"type": "URL", "host": "scam.cn"},
    ]
    base_payload["rules"]["TLD"] = [{"pattern": ".cn", "weight": 30}]
    result = score_report(base_payload)
    assert result["risk_score"] == 30

    # IP 25 > TLD 15 -> 25
    base_payload["rules"]["TLD"] = [{"pattern": ".cn", "weight": 15}]
    result2 = score_report(base_payload)
    assert result2["risk_score"] == 25


def test_shortener_exact_and_subdomain(base_payload):
    # Exact match bit.ly
    base_payload["indicators"] = [{"type": "URL", "host": "bit.ly"}]
    base_payload["rules"]["SHORTENER"] = [{"pattern": "bit.ly", "weight": 15}]
    result = score_report(base_payload)
    assert result["risk_score"] == 15

    # Subdomain match link.bit.ly
    base_payload["indicators"] = [{"type": "URL", "host": "link.bit.ly"}]
    result_sub = score_report(base_payload)
    assert result_sub["risk_score"] == 15

    # Negative: habit.ly does NOT match bit.ly
    base_payload["indicators"] = [{"type": "URL", "host": "habit.ly"}]
    result_neg = score_report(base_payload)
    assert result_neg["risk_score"] == 0


def test_prior_pending_points(base_payload):
    base_payload["prior_pending_counts"] = {"+60123456789": 3}
    result = score_report(base_payload)
    assert result["risk_score"] == 20


def test_high_priority_boundary(base_payload):
    # Score 74: kw 45 + tld 14 + shortener 15 = 74 -> is_high_priority = False
    base_payload["message_text"] = "urgent bank police"
    base_payload["rules"]["KEYWORD"] = [
        {"pattern": "urgent", "weight": 15},
        {"pattern": "bank", "weight": 15},
        {"pattern": "police", "weight": 15},
    ]  # kw = 45
    base_payload["indicators"] = [
        {"type": "URL", "host": "bad.xyz"},
        {"type": "URL", "host": "bit.ly"},
    ]
    base_payload["rules"]["TLD"] = [{"pattern": ".xyz", "weight": 14}]  # max(tld, ip) = 14
    base_payload["rules"]["SHORTENER"] = [{"pattern": "bit.ly", "weight": 15}]  # short = 15
    # Total = 45 + 14 + 15 = 74
    res74 = score_report(base_payload)
    assert res74["risk_score"] == 74
    assert res74["is_high_priority"] is False

    # Score 75: tld 15 -> total = 75 -> is_high_priority = True
    base_payload["rules"]["TLD"] = [{"pattern": ".xyz", "weight": 15}]
    res75 = score_report(base_payload)
    assert res75["risk_score"] == 75
    assert res75["is_high_priority"] is True


def test_total_score_capped_at_100(base_payload):
    base_payload["message_text"] = "urgent bank police"
    base_payload["rules"]["KEYWORD"] = [
        {"pattern": "urgent", "weight": 15},
        {"pattern": "bank", "weight": 15},
        {"pattern": "police", "weight": 15},
    ]  # 45
    base_payload["indicators"] = [
        {"type": "URL", "host": "192.168.1.1"},  # 25
        {"type": "URL", "host": "bit.ly"},  # 30
    ]
    base_payload["rules"]["SHORTENER"] = [{"pattern": "bit.ly", "weight": 30}]
    base_payload["prior_pending_counts"] = {"+60123456789": 2}  # 20
    # Sum = 45 + 25 + 30 + 20 = 120 -> capped at 100
    res = score_report(base_payload)
    assert res["risk_score"] == 100
    assert res["is_high_priority"] is True
