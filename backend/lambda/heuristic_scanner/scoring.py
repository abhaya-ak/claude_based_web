import ipaddress
import re


def _is_ip(host: str) -> bool:
    clean_host = host.strip("[]")
    try:
        ipaddress.ip_address(clean_host)
        return True
    except ValueError:
        return False


def score_report(p: dict) -> dict:
    """
    Pure heuristic scoring algorithm per spec (docs/03 lines 194-213).
    Zero DB, zero VPC, zero external dependencies.
    """
    cfg = p.get("config", {})
    rules = p.get("rules", {})
    text = (p.get("message_text") or "").lower()

    keyword_rules = rules.get("KEYWORD", [])
    tld_rules = rules.get("TLD", [])
    shortener_rules = rules.get("SHORTENER", [])

    items = []
    kw_points = 0
    for r in keyword_rules:
        pat = r["pattern"].lower()
        if re.search(rf"(?<!\w){re.escape(pat)}(?!\w)", text):
            kw_points += r["weight"]
            items.append({"rule": r["pattern"], "type": "KEYWORD", "points": r["weight"]})

    kw_cap = cfg.get("keyword_cap_points", 45)
    kw_final = min(kw_points, kw_cap)

    hosts = [
        i.get("host", "").lower().strip()
        for i in p.get("indicators", [])
        if i.get("type") in ("URL", "DOMAIN")
    ]

    # TLD matching
    matched_tlds = []
    for r in tld_rules:
        pat = r["pattern"].lower().strip()
        dot_pat = pat if pat.startswith(".") else "." + pat
        if any(h.endswith(dot_pat) for h in hosts if h):
            matched_tlds.append(r)

    max_tld_rule = max(matched_tlds, key=lambda x: x["weight"], default=None)
    tld_points = max_tld_rule["weight"] if max_tld_rule else 0

    # IP-based URL
    has_ip = any(_is_ip(h) for h in hosts if h)
    ip_url_points = cfg.get("ip_url_points", 25) if has_ip else 0

    # max(tld, ip_url)
    if tld_points >= ip_url_points:
        tld_ip_final = tld_points
        if max_tld_rule and tld_points > 0:
            items.append({"rule": max_tld_rule["pattern"], "type": "TLD", "points": tld_points})
    else:
        tld_ip_final = ip_url_points
        if ip_url_points > 0:
            items.append({"rule": "ip_url", "type": "IP_URL", "points": ip_url_points})

    # Shortener matching
    matched_shorteners = []
    for r in shortener_rules:
        pat = r["pattern"].lower().strip()
        dot_pat = "." + pat
        if any(h == pat or h.endswith(dot_pat) for h in hosts if h):
            matched_shorteners.append(r)

    max_short_rule = max(matched_shorteners, key=lambda x: x["weight"], default=None)
    short_points = max_short_rule["weight"] if max_short_rule else 0
    if max_short_rule and short_points > 0:
        items.append({"rule": max_short_rule["pattern"], "type": "SHORTENER", "points": short_points})

    # Prior pending points
    prior_counts = p.get("prior_pending_counts", {})
    prior_points = (
        cfg.get("prior_pending_points", 20)
        if any(v > 0 for v in prior_counts.values())
        else 0
    )
    if prior_points > 0:
        items.append({"rule": "prior_pending", "type": "PRIOR_PENDING", "points": prior_points})

    total_score = min(100, kw_final + tld_ip_final + short_points + prior_points)
    threshold = cfg.get("high_priority_threshold", 75)
    is_high_priority = total_score >= threshold

    return {
        "report_id": p.get("report_id"),
        "ruleset_version": p.get("ruleset_version"),
        "risk_score": total_score,
        "is_high_priority": is_high_priority,
        "breakdown": items,
    }
