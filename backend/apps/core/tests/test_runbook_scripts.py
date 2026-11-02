from pathlib import Path


def test_runbook_documentation_completeness():
    """D149: Assert docs/runbook.md exists and covers all required operational procedures."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    runbook_path = repo_root / "docs" / "runbook.md"

    assert runbook_path.exists(), "docs/runbook.md must exist"
    content = runbook_path.read_text(encoding="utf-8")

    # Required sections & operational topics
    required_topics = [
        "Zero-Downtime Rolling Deployment",
        "Single-Command Rollback",
        "RDS Point-in-Time Recovery",
        "Multi-AZ Failover Drill",
        "Zero-Downtime Secret Rotation",
        "Scheduled Operations & Cron Jobs",
        "Cost-Control Teardown / Scale-Down",
        "min_healthy_percentage",
        "Instance Refresh",
    ]
    for topic in required_topics:
        assert topic.lower() in content.lower(), f"Runbook missing section: {topic}"


def test_deployment_and_operational_scripts_exist():
    """Assert automation scripts exist in infra/scripts/ with proper execution commands."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    scripts_dir = repo_root / "infra" / "scripts"

    deploy_sh = scripts_dir / "deploy.sh"
    rollback_sh = scripts_dir / "rollback.sh"
    cost_down_sh = scripts_dir / "cost_down.sh"

    assert deploy_sh.exists(), "infra/scripts/deploy.sh must exist"
    assert rollback_sh.exists(), "infra/scripts/rollback.sh must exist"
    assert cost_down_sh.exists(), "infra/scripts/cost_down.sh must exist"

    # Verify content commands
    deploy_content = deploy_sh.read_text(encoding="utf-8")
    assert "start-instance-refresh" in deploy_content or "aws autoscaling" in deploy_content
    assert "migrate" in deploy_content

    rollback_content = rollback_sh.read_text(encoding="utf-8")
    assert "IMAGE_TAG" in rollback_content or "start-instance-refresh" in rollback_content

    cost_down_content = cost_down_sh.read_text(encoding="utf-8")
    assert "update-auto-scaling-group" in cost_down_content or "min-size 0" in cost_down_content
