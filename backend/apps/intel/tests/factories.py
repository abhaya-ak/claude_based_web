import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.intel.models import (
    IndicatorStatus,
    IndicatorType,
    ScamCategory,
    ThreatLevel,
    TriageAction,
    TriageDecision,
    VerifiedIndicator,
)
from apps.reports.tests.factories import ScamReportFactory


class VerifiedIndicatorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VerifiedIndicator

    type = IndicatorType.PHONE
    normalized_value = factory.Sequence(lambda n: f"+601234500{n:03d}")
    display_value = "+60•••••000"
    primary_category = ScamCategory.PHISHING
    threat_level = ThreatLevel.MEDIUM
    total_report_count = 1  # Set explicitly per Amendment B
    first_seen_at = factory.LazyFunction(timezone.now)
    last_seen_at = factory.LazyFunction(timezone.now)
    status = IndicatorStatus.ACTIVE
    public_note = ""  # Default empty string per Amendment C
    verified_by = factory.SubFactory(UserFactory, role="ANALYST")
    verified_at = factory.LazyFunction(timezone.now)
    revoked_by = None
    revoked_at = None
    revoke_reason = None


class TriageDecisionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TriageDecision

    report = factory.SubFactory(ScamReportFactory)
    analyst = factory.SubFactory(UserFactory, role="ANALYST")
    action = TriageAction.VERIFY
    indicator = factory.SubFactory(VerifiedIndicatorFactory)
    reason = None
