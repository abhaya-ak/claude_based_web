import hashlib
import json
import logging
import secrets

from django.conf import settings
from django.utils import timezone
from rest_framework import exceptions

from apps.alerts.models import AlertSubscription, Channel, SubscriptionStatus
from apps.core.aws import client
from apps.core.enums import AudienceGroup
from apps.reports.models import ScamCategory
from apps.reports.normalizers import NormalizationError, normalize_email, normalize_phone

logger = logging.getLogger(__name__)


def create_subscription(data: dict, user=None) -> tuple[AlertSubscription, str | None, bool]:
    """
    Creates an alert subscription per D104.
    - Validates channel (EMAIL, SMS). SMS requires ENABLE_SMS_ALERTS feature flag.
    - Normalizes endpoint.
    - Checks duplicate by (channel, endpoint_hash, audience). Duplicate returns existing row without leaking.
    - Subscribes to ALERTS_TOPIC_ARN via SNS with FilterPolicy.
    - Returns (subscription, raw_token, is_created).
    """
    channel = data.get("channel")
    raw_endpoint = data.get("endpoint", "")
    audience = data.get("audience")
    categories = data.get("categories") or []

    if channel not in Channel.values:
        raise exceptions.ValidationError({"channel": f"Invalid channel. Must be one of {Channel.values}."})

    if audience not in AudienceGroup.values:
        raise exceptions.ValidationError({"audience": f"Invalid audience. Must be one of {AudienceGroup.values}."})

    # Validate categories
    valid_categories = set(ScamCategory.values)
    for cat in categories:
        if cat not in valid_categories:
            raise exceptions.ValidationError({"categories": f"Invalid category '{cat}'."})

    # Channel-specific validation
    if channel == Channel.SMS:
        if not getattr(settings, "ENABLE_SMS_ALERTS", False):
            raise exceptions.ValidationError(
                {"channel": "SMS alerts are currently disabled in this environment."},
                code="sms_disabled",
            )
        try:
            cc = "ZZ" if raw_endpoint.strip().startswith("+") else "MY"
            normalized_endpoint, _ = normalize_phone(raw_endpoint, country_code=cc)
        except NormalizationError as exc:
            raise exceptions.ValidationError({"endpoint": exc.message}) from exc
    else:
        try:
            normalized_endpoint, _ = normalize_email(raw_endpoint)
        except NormalizationError as exc:
            raise exceptions.ValidationError({"endpoint": exc.message}) from exc

    endpoint_hash = hashlib.sha256(normalized_endpoint.encode("utf-8")).hexdigest()

    # Check for duplicate
    existing = AlertSubscription.objects.filter(
        channel=channel,
        endpoint_hash=endpoint_hash,
        audience=audience,
    ).first()
    if existing:
        return existing, None, False

    # Generate token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Subscribe to SNS
    topic_arn = getattr(
        settings,
        "ALERTS_TOPIC_ARN",
        "arn:aws:sns:ap-southeast-1:123456789012:scamshield-alerts",
    )
    protocol = "email" if channel == Channel.EMAIL else "sms"
    filter_policy = {"audience": ["ALL", audience]}
    if categories:
        filter_policy["category"] = list(categories)
    attributes = {"FilterPolicy": json.dumps(filter_policy)}

    sub_arn = None
    try:
        sns_client = client("sns")
        resp = sns_client.subscribe(
            TopicArn=topic_arn,
            Protocol=protocol,
            Endpoint=normalized_endpoint,
            Attributes=attributes,
            ReturnSubscriptionArn=True,
        )
        sub_arn = resp.get("SubscriptionArn")
    except Exception as exc:
        logger.warning("Failed to subscribe endpoint to SNS: %s", exc)

    sub = AlertSubscription.objects.create(
        user=user if (user and user.is_authenticated) else None,
        channel=channel,
        endpoint=normalized_endpoint,
        endpoint_hash=endpoint_hash,
        audience=audience,
        categories=categories,
        status=SubscriptionStatus.PENDING_CONFIRMATION,
        sns_subscription_arn=sub_arn,
        unsubscribe_token_hash=token_hash,
    )
    return sub, raw_token, True


def confirm_subscription(token: str) -> AlertSubscription:
    """Confirms subscription using token per D105."""
    if not token or not str(token).strip():
        raise exceptions.ValidationError({"token": "Token is required."})

    token_hash = hashlib.sha256(str(token).strip().encode("utf-8")).hexdigest()
    sub = AlertSubscription.objects.filter(unsubscribe_token_hash=token_hash).first()
    if not sub:
        raise exceptions.NotFound(
            detail="Invalid confirmation token or subscription not found.",
            code="subscription_not_found",
        )

    sub.status = SubscriptionStatus.ACTIVE
    sub.confirmed_at = timezone.now()
    sub.save(update_fields=["status", "confirmed_at"])
    return sub


def unsubscribe_subscription(token: str) -> AlertSubscription:
    """Unsubscribes from alert topic using token per D105."""
    if not token or not str(token).strip():
        raise exceptions.ValidationError({"token": "Token is required."})

    token_hash = hashlib.sha256(str(token).strip().encode("utf-8")).hexdigest()
    sub = AlertSubscription.objects.filter(unsubscribe_token_hash=token_hash).first()
    if not sub:
        raise exceptions.NotFound(
            detail="Invalid unsubscribe token or subscription not found.",
            code="subscription_not_found",
        )

    if sub.sns_subscription_arn and sub.sns_subscription_arn != "pending confirmation":
        try:
            sns_client = client("sns")
            sns_client.unsubscribe(SubscriptionArn=sub.sns_subscription_arn)
        except Exception as exc:
            logger.warning("Failed to unsubscribe from SNS: %s", exc)

    sub.status = SubscriptionStatus.UNSUBSCRIBED
    sub.unsubscribed_at = timezone.now()
    sub.save(update_fields=["status", "unsubscribed_at"])
    return sub
