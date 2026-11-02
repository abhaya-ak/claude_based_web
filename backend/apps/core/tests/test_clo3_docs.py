from pathlib import Path


def test_clo3_documentation_completeness():
    """D150: Assert docs/CLO3_ARCHITECTURE_HA_COST.md exists and covers all required academic topics."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    clo3_path = repo_root / "docs" / "CLO3_ARCHITECTURE_HA_COST.md"

    assert clo3_path.exists(), "docs/CLO3_ARCHITECTURE_HA_COST.md must exist"
    content = clo3_path.read_text(encoding="utf-8")

    # Required academic sections & criteria
    required_topics = [
        "CLO3",
        "High Availability",
        "2-AZ",
        "Recovery Time Objective",
        "Recovery Point Objective",
        "RTO",
        "RPO",
        "Origin Shielding",
        "X-CloudFront-Secret",
        "Origin Access Control",
        "AWS Pricing Calculator",
        "cost_down.sh",
    ]
    for topic in required_topics:
        assert topic.lower() in content.lower(), f"CLO3 document missing section or keyword: {topic}"
