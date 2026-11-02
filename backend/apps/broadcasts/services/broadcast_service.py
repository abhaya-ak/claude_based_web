import logging
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions, status

from apps.broadcasts.models import AdvisoryStatus, ThreatAdvisory
from apps.core.audit import log_event
from apps.core.aws import client
from apps.core.exceptions import ConflictError
from apps.core.metrics import emit

logger = logging.getLogger(__name__)


class SNSBroadcastFailed(exceptions.APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Failed to broadcast advisory to SNS topic."
    default_code = "sns_broadcast_failed"


def _post_publish_audit_and_metrics(advisory: ThreatAdvisory, user) -> None:
    """Non-blocking post-commit audit logging and CloudWatch metric emission."""
    try:
        log_event(
            "ADVISORY_PUBLISHED",
            actor=user,
            target=("ADVISORY", str(advisory.id)),
            metadata={
                "severity": advisory.severity,
                "target_audience": advisory.target_audience,
            },
        )
    except Exception as exc:
        logger.warning("Failed to audit ADVISORY_PUBLISHED for advisory %s: %s", advisory.id, exc)

    try:
        emit("AlertsPublished", 1, dims={"Environment": getattr(settings, "ENVIRONMENT", "test")})
    except Exception as exc:
        logger.warning("Failed to emit AlertsPublished metric for advisory %s: %s", advisory.id, exc)


def publish_advisory(advisory_id: UUID, user) -> ThreatAdvisory:
    """
    Publishes a threat advisory per D110.
    - Locks row via select_for_update() inside transaction.atomic().
    - Double-click publish is idempotent: raises 409 conflict if already PUBLISHED.
    - Publishes to settings.ALERTS_TOPIC_ARN with subject, body, and MessageAttributes.
    - On SNS failure, updates status to FAILED and clears timestamps (never leaves half-published state).
    - On success, updates status to PUBLISHED, records sns_message_id, audits event, and emits metric.
    """
    publish_failed = False
    publish_exc = None

    with transaction.atomic():
        advisory = ThreatAdvisory.objects.select_for_update().filter(id=advisory_id).first()
        if not advisory:
            raise exceptions.NotFound(
                detail="Advisory not found.",
                code="not_found",
            )

        if advisory.status == AdvisoryStatus.PUBLISHED:
            raise ConflictError(
                detail="Advisory has already been published.",
                code="advisory_already_published",
            )

        now = timezone.now()
        advisory.status = AdvisoryStatus.PUBLISHED
        advisory.published_by = user
        advisory.published_at = now
        advisory.save(update_fields=["status", "published_by", "published_at", "updated_at"])

        topic_arn = getattr(
            settings,
            "ALERTS_TOPIC_ARN",
            "arn:aws:sns:ap-southeast-1:123456789012:scamshield-alerts",
        )
        subject = f"[ScamShield Alert] {advisory.title}"[:100]
        message = advisory.body

        message_attributes = {
            "audience": {
                "DataType": "String",
                "StringValue": advisory.target_audience,
            }
        }
        if advisory.category:
            message_attributes["category"] = {
                "DataType": "String",
                "StringValue": advisory.category,
            }

        try:
            sns_client = client("sns")
            resp = sns_client.publish(
                TopicArn=topic_arn,
                Subject=subject,
                Message=message,
                MessageAttributes=message_attributes,
            )
            msg_id = resp.get("MessageId")
            advisory.sns_message_id = msg_id
            advisory.save(update_fields=["sns_message_id", "updated_at"])
            _post_publish_audit_and_metrics(advisory, user)
        except Exception as exc:
            logger.warning("Failed to publish advisory %s to SNS: %s", advisory.id, exc)
            advisory.status = AdvisoryStatus.FAILED
            advisory.published_by = None
            advisory.published_at = None
            advisory.sns_message_id = None
            advisory.save(update_fields=["status", "published_by", "published_at", "sns_message_id", "updated_at"])
            publish_failed = True
            publish_exc = exc

    if publish_failed:
        raise SNSBroadcastFailed() from publish_exc

    return advisory
