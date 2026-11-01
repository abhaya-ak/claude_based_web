import logging
from typing import Any

from apps.core.logging import FORBIDDEN_PII_KEYS, get_correlation_id
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog

logger = logging.getLogger(__name__)


def _check_for_pii(metadata: dict | None) -> None:
    if not metadata:
        return
    for key in metadata:
        key_lower = str(key).lower()
        for forbidden in FORBIDDEN_PII_KEYS:
            if forbidden in key_lower:
                raise ValueError(f"PII key '{key}' forbidden in audit metadata.")


def log_event(
    event_type: str,
    *,
    actor=None,
    ip_hash: str | None = None,
    target: Any = None,
    metadata: dict | None = None,
    severity: str = "INFO",
    request_id: str | None = None,
) -> SystemAuditLog | None:
    """Records security and operational actions to ops_systemauditlog.

    Validates event_type and severity against ops model enums.
    Refuses any forbidden PII keys in metadata (raises ValueError).
    Populates correlation request_id if not explicitly provided.
    """
    # Normalize string/enum values
    if hasattr(event_type, "value"):
        event_type = event_type.value
    if hasattr(severity, "value"):
        severity = severity.value

    # Validate event_type
    if event_type not in AuditEventType.values:
        raise ValueError(f"Invalid event_type '{event_type}'. Must be one of {AuditEventType.values}")

    # Validate severity
    if severity not in AuditSeverity.values:
        raise ValueError(f"Invalid severity '{severity}'. Must be one of {AuditSeverity.values}")

    # Check for PII
    _check_for_pii(metadata)

    # Correlation / Request ID
    final_request_id = request_id or get_correlation_id() or None

    # Target handling: satisfies DB constraint ((target_type IS NULL AND target_id IS NULL) OR (target_type IS NOT NULL AND target_id IS NOT NULL))
    target_type = ""
    target_id = ""
    if target is not None:
        if hasattr(target, "_meta"):
            target_type = target._meta.model_name
            target_id = str(target.pk)
        elif isinstance(target, (tuple, list)) and len(target) == 2:
            target_type = str(target[0])
            target_id = str(target[1]) if target[1] is not None else ""

    actor_user = actor if (actor and hasattr(actor, "pk")) else None

    return SystemAuditLog.objects.create(
        event_type=event_type,
        severity=severity,
        actor=actor_user,
        actor_ip_hash=ip_hash or "",
        target_type=target_type,
        target_id=target_id,
        metadata=metadata if metadata is not None else {},
        request_id=final_request_id,
    )
