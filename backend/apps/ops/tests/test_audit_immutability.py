import pytest
from django.db import DatabaseError, connection, transaction

from apps.accounts.tests.factories import UserFactory
from apps.core.audit import log_event
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog


@pytest.mark.django_db
class TestAuditImmutabilityTrigger:
    def test_to_be_proven_23_update_is_blocked_by_trigger(self):
        """TO BE PROVEN #23: Direct UPDATE on SystemAuditLog is prohibited by trigger."""
        user = UserFactory()
        log = log_event(
            event_type=AuditEventType.REPORT_SUBMITTED.value,
            actor=user,
            metadata={"detail": "initial"},
        )
        assert log is not None

        # Attempting to update severity or metadata must fail at the database level
        with pytest.raises(DatabaseError) as exc_info:
            with transaction.atomic():
                SystemAuditLog.objects.filter(id=log.id).update(severity=AuditSeverity.ALERT.value)

        assert "append-only" in str(exc_info.value).lower()

        # Attempting to update metadata must also fail
        with pytest.raises(DatabaseError) as exc_info:
            with transaction.atomic():
                log.metadata = {"detail": "tampered"}
                log.save()

        assert "append-only" in str(exc_info.value).lower()

    def test_to_be_proven_23_user_delete_set_null_succeeds(self):
        """TO BE PROVEN #23: Deleting a referenced User succeeds and sets actor_id = NULL."""
        user = UserFactory()
        log = log_event(
            event_type=AuditEventType.USER_REGISTERED.value,
            actor=user,
            metadata={"detail": "registered"},
        )
        assert log.actor_id == user.id

        # Deleting the user triggers ON DELETE SET NULL on actor_id
        # The trigger must allow this specific update
        user.delete()

        log.refresh_from_db()
        assert log.actor_id is None

    def test_to_be_proven_23_delete_is_blocked_outside_authorized_purge(self):
        """TO BE PROVEN #23: Direct DELETE without authorized session context is prohibited."""
        log = log_event(
            event_type=AuditEventType.RATE_LIMIT_BLOCK.value,
            metadata={"ip": "127.0.0.1"},
        )

        with pytest.raises(DatabaseError) as exc_info:
            with transaction.atomic():
                log.delete()

        assert "append-only" in str(exc_info.value).lower()

    def test_authorized_purge_setting_allows_delete_in_transaction_only(self):
        """Setting scamshield.audit_purge_allowed allows DELETE within the transaction only."""
        log = log_event(
            event_type=AuditEventType.LOGIN_FAILURE.value,
            metadata={"reason": "bad_password"},
        )

        # Inside transaction with audit_purge_allowed = 'on'
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET scamshield.audit_purge_allowed = 'on';")
            try:
                log.delete()
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("SET scamshield.audit_purge_allowed = 'off';")

        assert not SystemAuditLog.objects.filter(id=log.id).exists()

        # In a new transaction/after reset, DELETE is blocked again
        log2 = log_event(
            event_type=AuditEventType.LOGIN_FAILURE.value,
            metadata={"reason": "bad_password_2"},
        )
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                log2.delete()
