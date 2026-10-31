import factory

from apps.accounts.tests.factories import UserFactory
from apps.broadcasts.models import (
    AdvisorySeverity,
    AdvisoryStatus,
    ThreatAdvisory,
)
from apps.core.enums import AudienceGroup
from apps.reports.models import ScamCategory


class ThreatAdvisoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ThreatAdvisory

    title = factory.Sequence(lambda n: f"Threat Advisory #{n}: Phishing Alert")
    body = "Critical warning: New SMS phishing wave observed targeting banking users. Do not click links."
    sms_text = "ScamShield Alert: Fake bank SMS circulating. Never share OTPs."
    severity = AdvisorySeverity.WARNING
    target_audience = AudienceGroup.GENERAL
    category = ScamCategory.PHISHING
    related_indicator = None
    status = AdvisoryStatus.DRAFT
    sns_message_id = None
    created_by = factory.SubFactory(UserFactory, role="ANALYST")
    published_by = None
    published_at = None
