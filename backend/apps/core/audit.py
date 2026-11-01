import logging
from typing import Any

from django.utils import timezone

from apps.ops.models import AuditSeverity, SystemAuditLog

logger = logging.getLogger(__name__)

PII_KEYS = {"email", "password", "ip", "token", "refresh", "access"}


def log_event(
    event_type: str,
    *,
    actor: Any | None = None,
    ip_hash: str | None = None,
    target: tuple[str, Any] | None = None,
    metadata: dict | None = None,
    severity: str = AuditSeverity.INFO,
    request_id: str | None = None,
) -> SystemAuditLog | None:
    """
    Appends an event to the SystemAuditLog table.
    Guarantees no PII is saved in metadata. Never raises unexpected DB exceptions to caller.
    """
    clean_metadata = {}
    if metadata and isinstance(metadata, dict):
        for k, v in metadata.items():
            if k.lower() in PII_KEYS:
                continue
            clean_metadata[k] = v

    target_type = None
    target_id = None
    if target is not None:
        if isinstance(target, (tuple, list)) and len(target) == 2:
            target_type, tid = target
            target_id = str(tid) if tid is not None else None

    # Handle string severity or enum
    if hasattr(severity, "value"):
        severity = severity.value

    # Handle string event_type or enum
    if hasattr(event_type, "value"):
        event_type = event_type.value

    try:
        return SystemAuditLog.objects.create(
            occurred_at=timezone.now(),
            actor=actor,
            actor_ip_hash=ip_hash,
            event_type=event_type,
            severity=severity,
            target_type=target_type,
            target_id=target_id,
            metadata=clean_metadata,
            request_id=request_id,
        )
    except Exception as e:
        logger.error("Failed to write SystemAuditLog event %s: %s", event_type, e, exc_info=True)
        return None
