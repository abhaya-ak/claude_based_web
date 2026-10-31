import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import ApprovalStatus, Role, User
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestUserModelConstraints:
    def test_valid_citizen_creation(self):
        user = User.objects.create_user(
            email="citizen@example.com",
            password="StrongPassword123!",
            full_name="Ahmad Citizen",
            role=Role.CITIZEN,
        )
        assert user.email == "citizen@example.com"
        assert user.role == Role.CITIZEN
        assert user.approval_status == ApprovalStatus.APPROVED
        assert user.is_active is True
        assert user.is_superuser is False

    def test_valid_staff_creation(self):
        user = User.objects.create_user(
            email="analyst@example.com",
            password="StrongPassword123!",
            full_name="Fatima Analyst",
            role=Role.ANALYST,
            approval_status=ApprovalStatus.PENDING,
            organization="Cyber Threat Intel Unit",
            credential_note="Certified incident responder",
        )
        assert user.role == Role.ANALYST
        assert user.approval_status == ApprovalStatus.PENDING
        assert user.organization == "Cyber Threat Intel Unit"

    def test_unique_email_case_insensitive_fails(self):
        """Failing-insert test for uq_user_email_lower."""
        UserFactory(email="test.user@example.com")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                # Direct SQL insert or model insert with uppercase email
                User.objects.create(
                    email="TEST.USER@EXAMPLE.COM",
                    full_name="Duplicate User",
                    role=Role.CITIZEN,
                    approval_status=ApprovalStatus.APPROVED,
                )

    def test_invalid_role_check_constraint_fails(self):
        """Failing-insert test for ck_user_role."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create(
                    email="invalid_role@example.com",
                    full_name="Invalid Role User",
                    role="SUPERUSER",  # Not in Role.values
                    approval_status=ApprovalStatus.APPROVED,
                )

    def test_invalid_approval_status_check_constraint_fails(self):
        """Failing-insert test for ck_user_approval_status."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create(
                    email="invalid_status@example.com",
                    full_name="Invalid Status User",
                    role=Role.ANALYST,
                    approval_status="SUSPENDED",  # Not in ApprovalStatus.values
                )

    def test_citizen_must_be_approved_check_constraint_fails(self):
        """Failing-insert test for ck_user_citizen_approved (CITIZEN with PENDING status)."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create(
                    email="pending_citizen@example.com",
                    full_name="Pending Citizen",
                    role=Role.CITIZEN,
                    approval_status=ApprovalStatus.PENDING,  # Violates role='CITIZEN' -> approval_status='APPROVED'
                )

    def test_citizen_rejected_status_fails_check_constraint(self):
        """Failing-insert test for ck_user_citizen_approved (CITIZEN with REJECTED status)."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create(
                    email="rejected_citizen@example.com",
                    full_name="Rejected Citizen",
                    role=Role.CITIZEN,
                    approval_status=ApprovalStatus.REJECTED,
                )

    def test_manager_lowercases_email(self):
        """Amendment E: manager lowercases email on create_user."""
        user = User.objects.create_user(
            email="MixedCase.User@Example.COM",
            password="StrongPassword123!",
            full_name="Mixed Case User",
        )
        assert user.email == "mixedcase.user@example.com"

        refreshed = User.objects.get(pk=user.pk)
        assert refreshed.email == "mixedcase.user@example.com"

    def test_create_superuser_sets_right_flags(self):
        """Amendment E: create_superuser sets the right flags."""
        superuser = User.objects.create_superuser(
            email="Admin@Example.com",
            password="AdminPassword123!",
            full_name="System Administrator",
        )
        assert superuser.email == "admin@example.com"
        assert superuser.role == Role.ADMIN
        assert superuser.approval_status == ApprovalStatus.APPROVED
        assert superuser.is_superuser is True
        assert superuser.is_active is True
        assert superuser.is_staff is True

    def test_deleting_approver_sets_approved_by_null(self):
        """Amendment E: deleting an approver sets approved_by to NULL (SET_NULL)."""
        approver = UserFactory(
            role=Role.ADMIN,
            approval_status=ApprovalStatus.APPROVED,
            is_superuser=True,
        )
        staff = UserFactory(
            role=Role.ANALYST,
            approval_status=ApprovalStatus.APPROVED,
            approved_by=approver,
        )

        assert staff.approved_by == approver

        approver.delete()
        staff.refresh_from_db()
        assert staff.approved_by is None

    def test_str_never_exposes_pii(self):
        """docs/03a §11 checklist: __str__ never returns PII."""
        user = UserFactory(
            email="sensitive.citizen@example.com",
            full_name="Private Name",
            role=Role.CITIZEN,
        )
        user_str = str(user)
        assert "sensitive.citizen@example.com" not in user_str
        assert "Private Name" not in user_str
        assert str(user.id) in user_str
        assert "CITIZEN" in user_str
