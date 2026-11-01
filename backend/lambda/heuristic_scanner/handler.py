import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.request

try:
    from scoring import score_report
except ImportError:
    from .scoring import score_report

logger = logging.getLogger(__name__)


def lambda_handler(event: dict, context=None) -> dict:
    """
    AWS Lambda entrypoint for heuristic scanning.
    Executes scoring, signs payload with HMAC-SHA256, and POSTs to callback URL.
    """
    result = score_report(event)

    if context and hasattr(context, "aws_request_id"):
        result["lambda_request_id"] = str(context.aws_request_id)
    else:
        result["lambda_request_id"] = None

    callback_url = os.environ.get("SCANNER_CALLBACK_URL") or event.get("callback_url")
    secret = (
        os.environ.get("SCANNER_CALLBACK_SECRET")
        or os.environ.get("INTERNAL_CALLBACK_HMAC_KEY")
        or ""
    )

    body_bytes = json.dumps(result, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + body_bytes,
        hashlib.sha256,
    ).hexdigest()

    if callback_url:
        headers = {
            "Content-Type": "application/json",
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        }
        req = urllib.request.Request(
            callback_url,
            data=body_bytes,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                status_code = resp.getcode()
                logger.info("Callback returned HTTP %s for report %s", status_code, result.get("report_id"))
        except Exception as exc:
            logger.warning("Callback POST failed for report %s: %s", result.get("report_id"), exc)

    return {
        "statusCode": 200,
        "body": json.dumps(result),
    }
