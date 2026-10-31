import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.enums import AudienceGroup
from apps.reports.models import ScamCategory


class Channel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"


class SubscriptionStatus(models.TextChoices):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION", "Pending Confirmation"
    ACTIVE = "ACTIVE", "Active"
    UNSUBSCRIBED = "UNSUBSCRIBED", "Unsubscribed"
    FAILED = "FAILED", "Failed"


class AlertSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alert_subscriptions",
    )
    channel = models.CharField(max_length=5, choices=Channel.choices)
    endpoint = models.CharField(max_length=254)
    endpoint_hash = models.CharField(max_length=64)
    audience = models.CharField(max_length=15, choices=AudienceGroup.choices)
    categories = ArrayField(models.CharField(max_length=20), default=list, blank=True)
    status = models.CharField(
        max_length=22,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING_CONFIRMATION,
    )
    sns_subscription_arn = models.CharField(max_length=256, null=True, blank=True)
    unsubscribe_token_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "alerts_alertsubscription"
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "endpoint_hash", "audience"],
                name="uq_sub_channel_endpoint_aud",
            ),
            models.CheckConstraint(
                condition=models.Q(channel__in=Channel.values),
                name="ck_sub_channel",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=SubscriptionStatus.values),
                name="ck_sub_status",
            ),
            models.CheckConstraint(
                condition=models.Q(audience__in=AudienceGroup.values),
                name="ck_sub_audience",
            ),
            models.CheckConstraint(
                condition=models.Q(categories__contained_by=list(ScamCategory.values)),
                name="ck_sub_categories_elements",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "audience"],
                name="idx_sub_status_audience",
            ),
        ]

    def __str__(self):
        return f"AlertSubscription({self.id}, channel={self.channel}, audience={self.audience})"
