import logging

from django.conf import settings

from apps.core.aws import client

logger = logging.getLogger(__name__)

ALLOWED_METRIC_NAMES = {
    "ReportsSubmitted",
    "ReportsHighPriority",
    "AlertsPublished",
    "RateLimitBlocks",
    "ScanFailures",
    "LoginFailures",
    "ScanDispatched",
    "ScansCompleted",
    "ScansHighPriority",
    "ScansFailed",
}

ALLOWED_DIMENSION_NAMES = {
    "Environment",
    "Platform",
}


def emit(
    name: str,
    value: float = 1.0,
    unit: str = "Count",
    dims: dict[str, str] | None = None,
) -> None:
    """Emits CloudWatch custom metric in namespace 'ScamShield/Operations'.

    Fails safe and never raises exceptions per R-A6 / D32.
    """
    if not getattr(settings, "METRICS_ENABLED", False):
        return

    try:
        if name not in ALLOWED_METRIC_NAMES:
            logger.warning("Attempted to emit unlisted metric '%s'", name)
            return

        dimensions = []
        if dims:
            for k, v in dims.items():
                if k in ALLOWED_DIMENSION_NAMES:
                    dimensions.append({"Name": k, "Value": str(v)})

        cw = client("cloudwatch")
        cw.put_metric_data(
            Namespace="ScamShield/Operations",
            MetricData=[
                {
                    "MetricName": name,
                    "Value": float(value),
                    "Unit": unit,
                    "Dimensions": dimensions,
                }
            ],
        )
    except Exception as exc:
        logger.warning("Failed to emit CloudWatch metric '%s': %s", name, exc)
