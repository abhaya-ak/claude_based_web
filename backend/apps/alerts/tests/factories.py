import factory

from apps.accounts.tests.factories import UserFactory
from apps.alerts.models import (
    AlertSubscription,
    Channel,
    SubscriptionStatus,
)
from apps.core.enums import AudienceGroup


class AlertSubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AlertSubscription

    user = factory.SubFactory(UserFactory)
    channel = Channel.EMAIL
    endpoint = factory.Sequence(lambda n: f"subscriber{n}@example.com")
    endpoint_hash = factory.Sequence(lambda n: f"{n:064x}")
    audience = AudienceGroup.GENERAL
    categories = factory.LazyFunction(lambda: ["PHISHING", "FAKE_JOB"])
    status = SubscriptionStatus.PENDING_CONFIRMATION
    sns_subscription_arn = None
    unsubscribe_token_hash = factory.Sequence(lambda n: f"{n + 1:064x}")
