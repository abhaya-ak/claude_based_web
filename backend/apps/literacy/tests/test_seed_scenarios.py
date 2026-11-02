import io

import pytest
from django.core.management import call_command

from apps.accounts.models import ApprovalStatus, Role, User
from apps.literacy.models import ScenarioStatus, SimulatorScenario


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_seed_scenarios@scamshield.test",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
class TestSeedScenariosCommand:
    def test_seed_scenarios_idempotent(self, admin_user):
        out = io.StringIO()
        call_command("seed_scenarios", stdout=out)
        output = out.getvalue()
        assert "Seeded" in output or "already exists" in output or "scenarios" in output.lower()

        published_count = SimulatorScenario.objects.filter(status=ScenarioStatus.PUBLISHED).count()
        assert published_count >= 5  # At least 5 scenarios for simulator attempts

        # Running again does not duplicate or crash
        out2 = io.StringIO()
        call_command("seed_scenarios", stdout=out2)
        assert SimulatorScenario.objects.filter(status=ScenarioStatus.PUBLISHED).count() == published_count
