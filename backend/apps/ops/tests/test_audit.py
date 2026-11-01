import pytest
from django.db import IntegrityError, transaction

from apps.accounts.tests.factories import UserFactory
from apps.core.audit import log_event
from apps.ops.models import AuditEventType, AuditSeverity
from apps.ops.tests.factories import SystemAuditLogFactory


@pytest.mark.django_db
class TestAuditWriterAndNewEventTypes:
    def test_new_audit_event_types_in_db(self):
        """D42: DB constraint ck_audit_event_type must allow the 3 new types."""
        # 3 new types: USER_REGISTERED, ROLE_CHANGED, PASSWORD_CHANGED
        for event_type in [
            AuditEventType.USER_REGISTERED,
            AuditEventType.ROLE_CHANGED,
            AuditEventType.PASSWORD_CHANGED,
        ]:
            log = SystemAuditLogFactory(event_type=event_type)
            assert log.event_type == event_type

        # Invalid type fails
        with pytest.raises(IntegrityError) as exc:
            with transaction.atomic():
                SystemAuditLogFactory(event_type="UNAPPROVED_CUSTOM_EVENT")
        assert "ck_audit_event_type" in str(exc.value)

    def test_log_event_helper(self):
        actor = UserFactory()
        log = log_event(
            event_type=AuditEventType.USER_REGISTERED,
            actor=actor,
            ip_hash="f" * 64,
            target=("USER", str(actor.id)),
            metadata={"source": "self_service"},
            severity=AuditSeverity.INFO,
            request_id="req-1234",
        )
        assert log is not None
        assert log.event_type == AuditEventType.USER_REGISTERED
        assert log.actor_id == actor.id
        assert log.actor_ip_hash == "f" * 64
        assert log.target_type == "USER"
        assert log.target_id == str(actor.id)
        assert log.metadata == {"source": "self_service"}
        assert log.request_id == "req-1234"

    def test_log_event_pii_scrubbing(self):
        """Defense-in-depth: metadata with PII keys should be stripped/rejected."""
        log = log_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            ip_hash="0" * 64,
            metadata={
                "email": "victim@example.com",
                "password": "secretpassword",
                "ip": "1.2.3.4",
                "token": "secret_jwt",
                "refresh": "refresh_token",
                "access": "access_token",
                "safe_key": "safe_value",
            },
        )
        assert log is not None
        # PII keys must be stripped
        for key in ["email", "password", "ip", "token", "refresh", "access"]:
            assert key not in log.metadata
        assert log.metadata.get("safe_key") == "safe_value"
