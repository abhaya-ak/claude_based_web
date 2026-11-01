import json
import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.core import metrics
from apps.core.aws import client
from apps.reports.models import ScamReport, ScanStatus
from apps.scanner.models import ScanResult

logger = logging.getLogger(__name__)


def process_scan_result(
    report_id: uuid.UUID | str,
    ruleset_version: int,
    risk_score: int,
    is_high_priority: bool,
    breakdown: list,
    lambda_request_id: str | None = None,
) -> tuple[ScanResult, ScamReport]:
    """
    Persists scan results, updates ScamReport, and triggers high-priority SNS alerts (D91).
    Guarantees:
    - Atomicity & idempotency per (report_id, ruleset_version).
    - Failure tolerance on SNS alert publishing.
    - Zero PII in SNS alert messages.
    """
    with transaction.atomic():
        try:
            report = ScamReport.objects.select_for_update().get(id=report_id)
        except ScamReport.DoesNotExist as err:
            raise exceptions.NotFound(f"Report {report_id} not found.") from err

        # Idempotency and version check
        existing_result = ScanResult.objects.filter(report=report).first()
        if existing_result:
            if existing_result.ruleset_version == ruleset_version:
                # Idempotent replay: return 200 OK without modifying DB or re-sending alerts
                return existing_result, report

            if ruleset_version > existing_result.ruleset_version:
                existing_result.ruleset_version = ruleset_version
                existing_result.risk_score = risk_score
                existing_result.is_high_priority = is_high_priority
                existing_result.breakdown = breakdown
                if lambda_request_id is not None:
                    existing_result.lambda_request_id = lambda_request_id
                existing_result.scanned_at = timezone.now()
                existing_result.save()
                scan_result = existing_result
            else:
                # Older ruleset version arrived after a newer one; do not overwrite ScamReport
                return existing_result, report
        else:
            scan_result = ScanResult.objects.create(
                report=report,
                ruleset_version=ruleset_version,
                risk_score=risk_score,
                is_high_priority=is_high_priority,
                breakdown=breakdown,
                lambda_request_id=lambda_request_id,
            )

        # Update ScamReport fields
        report.risk_score = risk_score
        report.is_high_priority = is_high_priority
        report.scan_status = ScanStatus.DONE
        report.save(update_fields=["risk_score", "is_high_priority", "scan_status", "updated_at"])

        # Operational metrics and staff alerts post-commit
        def _on_commit():
            metrics.emit("ScansCompleted", 1)
            if is_high_priority:
                metrics.emit("ScansHighPriority", 1)
                topic_arn = getattr(settings, "STAFF_TOPIC_ARN", None)
                if topic_arn:
                    try:
                        sns_cli = client("sns")
                        # Strictly operational metadata: ZERO PII per D68 / D91
                        msg_payload = {
                            "reference_code": report.reference_code,
                            "report_id": str(report.id),
                            "category": report.category,
                            "risk_score": risk_score,
                            "ruleset_version": ruleset_version,
                        }
                        sns_cli.publish(
                            TopicArn=topic_arn,
                            Subject=f"ScamShield Alert: High Priority Report {report.reference_code}",
                            Message=json.dumps(msg_payload),
                        )
                    except Exception as exc:
                        logger.exception(
                            "Failed to publish staff alert SNS for report %s: %s",
                            report.id,
                            exc,
                        )

        transaction.on_commit(_on_commit)

    return scan_result, report
