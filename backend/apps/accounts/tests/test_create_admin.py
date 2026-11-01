from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import ApprovalStatus, Role, User
from apps.ops.models import SystemAuditLog


@pytest.mark.django_db
class TestCreateAdminCommand:
    def test_create_admin_with_env_password_success(self, monkeypatch):
        monkeypatch.setenv("ADMIN_PASSWORD", "SuperSecurePassword123!")
        out = StringIO()
        call_command(
            "create_admin",
            "--email", "Admin.System@example.com",
            "--full-name", "Primary Admin",
            stdout=out,
        )

        admin = User.objects.get(email="admin.system@example.com")
        assert admin.role == Role.ADMIN
        assert admin.approval_status == ApprovalStatus.APPROVED
        assert admin.is_active is True
        assert admin.full_name == "Primary Admin"
        assert admin.check_password("SuperSecurePassword123!") is True

        # Audit row
        assert SystemAuditLog.objects.filter(
            target_type="USER",
            target_id=str(admin.id),
        ).exists()

    def test_create_admin_idempotent_promotes_existing_user(self, monkeypatch):
        monkeypatch.setenv("ADMIN_PASSWORD", "SuperSecurePassword123!")
        # Existing citizen user
        user = User.objects.create_user(
            email="citizen_to_promote@example.com",
            password="InitialPassword123!",
            full_name="To Promote",
            role=Role.CITIZEN,
            approval_status=ApprovalStatus.APPROVED,
        )

        out = StringIO()
        call_command(
            "create_admin",
            "--email", "citizen_to_promote@example.com",
            stdout=out,
        )

        user.refresh_from_db()
        assert user.role == Role.ADMIN
        assert user.approval_status == ApprovalStatus.APPROVED
        assert user.check_password("SuperSecurePassword123!") is True

        # Re-running again does not crash or duplicate
        call_command(
            "create_admin",
            "--email", "citizen_to_promote@example.com",
            stdout=out,
        )
        assert User.objects.filter(email="citizen_to_promote@example.com").count() == 1

    def test_create_admin_weak_password_rejected(self, monkeypatch):
        monkeypatch.setenv("ADMIN_PASSWORD", "short")
        with pytest.raises(CommandError) as exc:
            call_command("create_admin", "--email", "weak_admin@example.com")
        assert "password" in str(exc.value).lower()

    def test_create_admin_no_input_without_env_password_fails(self, monkeypatch):
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        with pytest.raises(CommandError) as exc:
            call_command("create_admin", "--email", "noinput_admin@example.com", "--no-input")
        assert "ADMIN_PASSWORD" in str(exc.value)
