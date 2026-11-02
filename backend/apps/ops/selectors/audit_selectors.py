import uuid
from datetime import datetime, time

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import ValidationError

from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog


def _parse_iso_or_date(val: str, is_end_of_day: bool = False):
    if not val:
        return None
    cleaned = str(val).strip().replace(" ", "+")
    parsed = parse_datetime(cleaned)
    if parsed:
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
    d = parse_date(cleaned)
    if d:
        target_time = time.max if is_end_of_day else time.min
        return timezone.make_aware(datetime.combine(d, target_time))
    return None


def filter_audit_logs(
    *,
    event_type: str | None = None,
    severity: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    actor_id: str | None = None,
    ip_hash: str | None = None,
) -> QuerySet[SystemAuditLog]:
    """
    Filters SystemAuditLog queryset with strict input validation.
    Enforces minimum 8 chars for ip_hash prefix.
    Uses select_related('actor') for query bounding.
    """
    qs = SystemAuditLog.objects.select_related("actor").order_by("-occurred_at", "-id")

    if event_type:
        if event_type not in AuditEventType.values:
            raise ValidationError({"event_type": [f"Invalid event_type '{event_type}'."]})
        qs = qs.filter(event_type=event_type)

    if severity:
        if severity not in AuditSeverity.values:
            raise ValidationError({"severity": [f"Invalid severity '{severity}'."]})
        qs = qs.filter(severity=severity)

    parsed_from = None
    if date_from:
        parsed_from = _parse_iso_or_date(date_from, is_end_of_day=False)
        if not parsed_from:
            raise ValidationError({"date_from": ["Invalid date_from format. Use ISO 8601."]})
        qs = qs.filter(occurred_at__gte=parsed_from)

    parsed_to = None
    if date_to:
        parsed_to = _parse_iso_or_date(date_to, is_end_of_day=True)
        if not parsed_to:
            raise ValidationError({"date_to": ["Invalid date_to format. Use ISO 8601."]})
        qs = qs.filter(occurred_at__lte=parsed_to)

    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise ValidationError({"date_from": ["date_from cannot be after date_to."]})

    if actor_id:
        try:
            actor_uuid = uuid.UUID(str(actor_id))
        except (ValueError, TypeError):
            raise ValidationError({"actor_id": ["Invalid actor_id UUID."]}) from None
        qs = qs.filter(actor_id=actor_uuid)

    if ip_hash:
        clean_ip_hash = str(ip_hash).strip().lower()
        if len(clean_ip_hash) < 8:
            raise ValidationError({"ip_hash": ["ip_hash filter must be at least 8 characters long."]})
        qs = qs.filter(actor_ip_hash__startswith=clean_ip_hash)

    return qs
