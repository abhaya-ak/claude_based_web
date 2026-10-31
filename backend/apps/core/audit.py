from typing import Any

from apps.core.logging import FORBIDDEN_PII_KEYS, get_correlation_id


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
):
    """Records security and operational actions to ops_systemauditlog.

    Lazy imports ops models inside the function to avoid circular imports.
    Validates event_type and severity against ops model enums.
    Refuses any forbidden PII keys in metadata.
    """
    # Lazy import per user instruction
    from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog

    # Validate event_type
    if event_type not in AuditEventType.values:
        raise ValueError(f"Invalid event_type '{event_type}'. Must be one of {AuditEventType.values}")

    # Validate severity
    if severity not in AuditSeverity.values:
        raise ValueError(f"Invalid severity '{severity}'. Must be one of {AuditSeverity.values}")

    # Check for PII
    _check_for_pii(metadata)

    # Correlation / Request ID
    final_request_id = request_id or get_correlation_id()

    # Target handling
    target_type = ""
    target_id = ""
    if target is not None:
        if hasattr(target, "_meta"):
            target_type = target._meta.model_name
            target_id = str(target.pk)
        elif isinstance(target, tuple) and len(target) == 2:
            target_type = str(target[0])
            target_id = str(target[1])

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
