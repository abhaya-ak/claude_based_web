from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connection

from apps.accounts.models import Role, User
from apps.broadcasts.models import ThreatAdvisory
from apps.intel.models import VerifiedIndicator
from apps.literacy.models import SimulatorAttempt, SimulatorScenario
from apps.reports.models import ScamReport


@pytest.mark.django_db
class TestSeedDemoCommand:
    """
    Tests for D136:
    - seed_demo refuses to run without --i-know-what-i-am-doing flag.
    - seed_demo refuses to run if DEBUG is False.
    - seed_demo refuses to run on non-local database host.
    - seed_demo refuses to run without password from environment variable.
    - seed_demo small scale is idempotent.
    - SQL integrity checks report 0 violations after seed.
    """

    def test_refuses_without_flag(self, monkeypatch):
        monkeypatch.setenv("SEED_DEMO_PASSWORD", "ValidDemoPass123!")
        with pytest.raises(CommandError, match="--i-know-what-i-am-doing"):
            call_command("seed_demo")

    def test_refuses_when_debug_false(self, monkeypatch):
        monkeypatch.setenv("SEED_DEMO_PASSWORD", "ValidDemoPass123!")
        monkeypatch.setattr(settings, "DEBUG", False)
        with pytest.raises(CommandError, match="DEBUG is False"):
            call_command("seed_demo", "--i-know-what-i-am-doing")

    def test_refuses_when_db_host_non_local(self, monkeypatch):
        monkeypatch.setattr(settings, "DEBUG", True)
        monkeypatch.setenv("SEED_DEMO_PASSWORD", "ValidDemoPass123!")
        db_copy = settings.DATABASES.copy()
        db_copy["default"] = dict(db_copy["default"])
        db_copy["default"]["HOST"] = "remote.rds.amazonaws.com"
        monkeypatch.setattr(settings, "DATABASES", db_copy)

        with pytest.raises(CommandError, match="non-local database host"):
            call_command("seed_demo", "--i-know-what-i-am-doing")

    def test_refuses_without_env_password(self, monkeypatch):
        monkeypatch.setattr(settings, "DEBUG", True)
        monkeypatch.delenv("SEED_DEMO_PASSWORD", raising=False)
        monkeypatch.delenv("DEMO_PASSWORD", raising=False)
        with pytest.raises(CommandError, match="SEED_DEMO_PASSWORD"):
            call_command("seed_demo", "--i-know-what-i-am-doing")

    def test_small_scale_idempotent_and_creates_all_entities(self, monkeypatch):
        monkeypatch.setenv("SEED_DEMO_PASSWORD", "ValidDemoPass123!")
        monkeypatch.setattr(settings, "DEBUG", True)

        # First run
        call_command("seed_demo", "--i-know-what-i-am-doing", "--scale=small")

        # Verify users exist for all 4 roles
        assert User.objects.filter(role=Role.ADMIN).exists()
        assert User.objects.filter(role=Role.ANALYST).exists()
        assert User.objects.filter(role=Role.EDUCATOR).exists()
        assert User.objects.filter(role=Role.CITIZEN).exists()

        # Verify core demo entities exist
        assert ScamReport.objects.exists()
        assert VerifiedIndicator.objects.exists()
        assert ThreatAdvisory.objects.exists()
        assert SimulatorScenario.objects.exists()
        assert SimulatorAttempt.objects.exists()

        counts_after_first_run = {
            "users": User.objects.count(),
            "reports": ScamReport.objects.count(),
            "indicators": VerifiedIndicator.objects.count(),
            "advisories": ThreatAdvisory.objects.count(),
            "scenarios": SimulatorScenario.objects.count(),
        }

        # Second run (idempotency check)
        call_command("seed_demo", "--i-know-what-i-am-doing", "--scale=small")

        counts_after_second_run = {
            "users": User.objects.count(),
            "reports": ScamReport.objects.count(),
            "indicators": VerifiedIndicator.objects.count(),
            "advisories": ThreatAdvisory.objects.count(),
            "scenarios": SimulatorScenario.objects.count(),
        }

        assert counts_after_first_run == counts_after_second_run

    def test_sql_integrity_checks_pass_cleanly(self, monkeypatch):
        monkeypatch.setenv("SEED_DEMO_PASSWORD", "ValidDemoPass123!")
        monkeypatch.setattr(settings, "DEBUG", True)

        call_command("seed_demo", "--i-know-what-i-am-doing", "--scale=small")

        sql_path = Path(__file__).resolve().parent.parent.parent.parent / "tools" / "qa_sql_checks.sql"
        assert sql_path.exists()
        raw_sql = sql_path.read_text(encoding="utf-8")

        queries = [
            q.strip()
            for q in raw_sql.split(";")
            if q.strip() and not q.strip().startswith("--")
        ]

        with connection.cursor() as cursor:
            for query in queries:
                # filter out comment-only chunks
                clean_query = "\n".join(
                    line for line in query.splitlines() if not line.strip().startswith("--")
                ).strip()
                if not clean_query:
                    continue
                cursor.execute(clean_query)
                violations = cursor.fetchall()
                assert len(violations) == 0, f"Integrity check failed: {clean_query} returned {violations}"

    @pytest.mark.slow
    def test_load_scale_generation(self, monkeypatch):
        monkeypatch.setenv("SEED_DEMO_PASSWORD", "ValidDemoPass123!")
        monkeypatch.setattr(settings, "DEBUG", True)

        call_command("seed_demo", "--i-know-what-i-am-doing", "--scale=load")

        assert ScamReport.objects.count() >= 20000
        assert SimulatorAttempt.objects.exists()

