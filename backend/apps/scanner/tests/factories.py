import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.reports.tests.factories import ScamReportFactory
from apps.scanner.models import (
    HeuristicRule,
    RuleType,
    ScannerConfig,
    ScanResult,
)


class HeuristicRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HeuristicRule

    rule_type = RuleType.KEYWORD
    pattern = factory.Sequence(lambda n: f"urgent-{n}")
    weight = 15
    is_active = True
    created_by = factory.SubFactory(UserFactory, role="ADMIN")


class ScannerConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ScannerConfig
        django_get_or_create = ("id",)

    id = 1
    keyword_cap_points = 45
    ip_url_points = 25
    prior_pending_points = 20
    high_priority_threshold = 75
    ruleset_version = 1
    updated_by = None


class ScanResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ScanResult

    report = factory.SubFactory(ScamReportFactory)
    ruleset_version = 1
    risk_score = 50
    breakdown = factory.LazyFunction(lambda: [{"rule": "urgent", "type": "KEYWORD", "points": 15}])
    is_high_priority = False
    lambda_request_id = None
    scanned_at = factory.LazyFunction(timezone.now)
