import json
import logging
import uuid

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.core import aws
from apps.reports.models import ScamReport
from apps.scanner.selectors.scanner_selectors import build_scan_payload

logger = logging.getLogger(__name__)


def dispatch_scan(report_id: uuid.UUID) -> None:
    """
    Contract 3.5: collects report narrative, indicators, active rules, config, and prior counts.
    Invokes Lambda scanner asynchronously via boto3 Lambda client.
    Non-blocking and failure-tolerant per R-A6 / D88: failures never roll back report creation.
    """
    try:
        payload = build_scan_payload(report_id)
        function_name = getattr(
            settings, "SCANNER_LAMBDA_FUNCTION_NAME", "scamshield-heuristic-scanner"
        )
        lambda_client = aws.client("lambda")
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
        ScamReport.objects.filter(id=report_id).update(
            scan_dispatched_at=timezone.now(),
            scan_attempts=F("scan_attempts") + 1,
        )
        logger.info("Dispatched scan for report %s", report_id)
    except Exception as exc:
        # Never raise to caller; update scan_attempts for tracking
        logger.warning("Scan dispatch failed for report %s: %s", report_id, exc)
        try:
            ScamReport.objects.filter(id=report_id).update(
                scan_attempts=F("scan_attempts") + 1,
            )
        except Exception as update_exc:
            logger.debug("Failed to increment scan_attempts on report %s: %s", report_id, update_exc)
