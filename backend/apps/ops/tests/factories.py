import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.ops.models import (
    AuditEventType,
    AuditSeverity,
    SystemAuditLog,
)


class SystemAuditLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SystemAuditLog

    occurred_at = factory.LazyFunction(timezone.now)
    actor = factory.SubFactory(UserFactory, role="CITIZEN")
    actor_ip_hash = factory.Sequence(lambda n: f"{n:064x}")
    event_type = AuditEventType.REPORT_SUBMITTED
    severity = AuditSeverity.INFO
    target_type = None
    target_id = None
    metadata = factory.LazyFunction(dict)
    request_id = factory.Sequence(lambda n: f"req-{n}")
