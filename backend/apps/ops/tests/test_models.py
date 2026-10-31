import pytest
from django.db import IntegrityError, transaction

from apps.accounts.tests.factories import UserFactory
from apps.ops.models import (
    AuditEventType,
    AuditSeverity,
    SystemAuditLog,
)
from apps.ops.tests.factories import SystemAuditLogFactory


@pytest.mark.django_db
class TestSystemAuditLogConstraints:
    def test_invalid_event_type_fails(self):
        """Failing-insert test for ck_audit_event_type."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SystemAuditLogFactory(event_type="INVALID_EVENT")
        assert "ck_audit_event_type" in str(excinfo.value)

        # Positive control: valid event_type succeeds
        valid = SystemAuditLogFactory(event_type=AuditEventType.REPORT_SUBMITTED)
        assert valid.event_type == AuditEventType.REPORT_SUBMITTED

    def test_invalid_severity_fails(self):
        """Failing-insert test for ck_audit_severity."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SystemAuditLogFactory(severity="FATAL")
        assert "ck_audit_severity" in str(excinfo.value)

        # Positive control: valid severity succeeds
        valid = SystemAuditLogFactory(severity=AuditSeverity.WARN)
        assert valid.severity == AuditSeverity.WARN

    def test_metadata_is_json_object(self):
        """D18 & Amendment E: jsonb_typeof(metadata) = 'object'."""
        # Failing case 1: JSON list []
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SystemAuditLogFactory(metadata=[])
        assert "ck_audit_metadata_is_object" in str(excinfo.value)

        # Failing case 2: JSON string
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SystemAuditLogFactory(metadata="string_value")
        assert "ck_audit_metadata_is_object" in str(excinfo.value)

        # Positive control 1: empty dict {}
        valid_empty = SystemAuditLogFactory(metadata={})
        assert valid_empty.metadata == {}

        # Positive control 2: dict with key-value pairs
        valid_dict = SystemAuditLogFactory(metadata={"ip": "127.0.0.1", "action": "test"})
        assert valid_dict.metadata["action"] == "test"

    def test_metadata_none_behavior(self):
        """Amendment E: Test metadata=None to report whether NOT NULL or check constraint fires."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SystemAuditLogFactory(metadata=None)
        err = str(excinfo.value).lower()
        # Column has NOT NULL, so PostgreSQL raises not-null constraint violation
        assert "null" in err and "metadata" in err

    def test_target_pair_rules(self):
        """D18: target_type and target_id must be both NULL or both set."""
        # Failing case 1: target_type set, target_id None
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SystemAuditLogFactory(target_type="REPORT", target_id=None)
        assert "ck_audit_target_pair" in str(excinfo.value)

        # Failing case 2: target_type None, target_id set
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                SystemAuditLogFactory(target_type=None, target_id="target-uuid-123")
        assert "ck_audit_target_pair" in str(excinfo.value)

        # Positive control 1: both None succeeds
        valid_both_none = SystemAuditLogFactory(target_type=None, target_id=None)
        assert valid_both_none.target_type is None
        assert valid_both_none.target_id is None

        # Positive control 2: both set succeeds
        valid_both_set = SystemAuditLogFactory(target_type="REPORT", target_id="target-uuid-123")
        assert valid_both_set.target_type == "REPORT"
        assert valid_both_set.target_id == "target-uuid-123"


@pytest.mark.django_db
class TestSystemAuditLogRelationshipsAndPrivacy:
    def test_actor_set_null(self):
        """on_delete SET_NULL on SystemAuditLog.actor nulls actor_id."""
        actor = UserFactory(role="CITIZEN")
        log = SystemAuditLogFactory(actor=actor)
        log_id = log.id

        actor.delete()

        log.refresh_from_db()
        assert log.actor_id is None
        assert SystemAuditLog.objects.filter(id=log_id).exists()

    def test_privacy_audit_log_str(self):
        """SystemAuditLog.__str__ must not leak metadata or actor_ip_hash."""
        secret_ip_hash = "secret_ip_hash_string_abcdef1234567890"
        secret_meta_val = "SECRET_METADATA_DATA"
        log = SystemAuditLogFactory(
            actor_ip_hash=secret_ip_hash,
            metadata={"confidential": secret_meta_val},
            event_type=AuditEventType.REPORT_SUBMITTED,
        )
        str_rep = str(log)
        assert "REPORT_SUBMITTED" in str_rep
        assert secret_ip_hash not in str_rep
        assert secret_meta_val not in str_rep
