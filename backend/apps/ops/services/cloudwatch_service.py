import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.core.aws import client
from apps.core.metrics import ALLOWED_DIMENSION_NAMES, ALLOWED_METRIC_NAMES

logger = logging.getLogger(__name__)

VALID_TIME_RANGES = {
    "1h": (timedelta(hours=1), 60),
    "6h": (timedelta(hours=6), 300),
    "24h": (timedelta(hours=24), 300),
    "7d": (timedelta(days=7), 3600),
}


def put_metrics(metric_data: list[dict[str, Any]], namespace: str = "ScamShield/Operations") -> bool:
    """
    Batches metric data into chunks of at most 20 datums and emits them to CloudWatch.
    Enforces low-cardinality dimensions and timeout constraints.
    Catches all AWS/network exceptions, logs warnings, and returns False on failure (non-raising per R-A6).
    """
    if not getattr(settings, "METRICS_ENABLED", False):
        return True

    if not metric_data:
        return True

    try:
        formatted_items = []
        for item in metric_data:
            name = item.get("name") or item.get("MetricName")
            if not name or name not in ALLOWED_METRIC_NAMES:
                continue

            val = float(item.get("value", item.get("Value", 1.0)))
            unit = item.get("unit", item.get("Unit", "Count"))

            raw_dims = item.get("dims") or item.get("Dimensions") or {}
            dimensions = []
            if isinstance(raw_dims, dict):
                for k, v in raw_dims.items():
                    if k in ALLOWED_DIMENSION_NAMES:
                        dimensions.append({"Name": k, "Value": str(v)})
            elif isinstance(raw_dims, list):
                for d in raw_dims:
                    if isinstance(d, dict) and d.get("Name") in ALLOWED_DIMENSION_NAMES:
                        dimensions.append({"Name": d["Name"], "Value": str(d.get("Value", ""))})

            formatted_items.append(
                {
                    "MetricName": name,
                    "Value": val,
                    "Unit": unit,
                    "Dimensions": dimensions,
                }
            )

        if not formatted_items:
            return True

        cw = client("cloudwatch")
        chunk_size = 20
        for i in range(0, len(formatted_items), chunk_size):
            chunk = formatted_items[i : i + chunk_size]
            cw.put_metric_data(
                Namespace=namespace,
                MetricData=chunk,
            )
        return True
    except Exception as exc:
        logger.warning("Failed to put metrics to CloudWatch namespace '%s': %s", namespace, exc)
        return False


def get_dashboard_series(time_range: str = "24h", period: int | None = None) -> dict[str, Any]:
    """
    Fetches chart-ready metric series from CloudWatch across infrastructure and operational metrics.
    Caches successful responses in Django cache for 60 seconds (D34/R-E4).
    Catches all exceptions and returns a degraded response structure (never raises 500 per R-A6).
    """
    if time_range not in VALID_TIME_RANGES:
        raise ValueError(f"Invalid time_range '{time_range}'. Must be one of {list(VALID_TIME_RANGES.keys())}.")

    default_delta, default_period = VALID_TIME_RANGES[time_range]
    selected_period = period or default_period
    cache_key = f"ops:telemetry:series:{time_range}:{selected_period}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    now = timezone.now()
    start_time = now - default_delta

    degraded_response = {
        "time_range": time_range,
        "period": selected_period,
        "generated_at": now.isoformat(),
        "degraded": True,
        "infrastructure": {
            "ec2": {"cpu": []},
            "alb": {"5xx": [], "latency": [], "healthy_hosts": []},
            "rds": {"cpu": [], "connections": [], "free_storage": [], "free_memory": []},
        },
        "operations": {
            "reports_submitted": [],
            "reports_high_priority": [],
            "alerts_published": [],
            "rate_limit_blocks": [],
            "scan_failures": [],
            "login_failures": [],
        },
    }

    try:
        queries = [
            # EC2
            {
                "Id": "ec2_cpu",
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/EC2", "MetricName": "CPUUtilization"},
                    "Period": selected_period,
                    "Stat": "Average",
                    "Unit": "Percent",
                },
                "ReturnData": True,
            },
            # ALB
            {
                "Id": "alb_5xx",
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/ApplicationELB", "MetricName": "HTTPCode_Target_5XX_Count"},
                    "Period": selected_period,
                    "Stat": "Sum",
                    "Unit": "Count",
                },
                "ReturnData": True,
            },
            {
                "Id": "alb_latency",
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/ApplicationELB", "MetricName": "TargetResponseTime"},
                    "Period": selected_period,
                    "Stat": "Average",
                    "Unit": "Seconds",
                },
                "ReturnData": True,
            },
            {
                "Id": "alb_healthy_hosts",
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/ApplicationELB", "MetricName": "HealthyHostCount"},
                    "Period": selected_period,
                    "Stat": "Average",
                    "Unit": "Count",
                },
                "ReturnData": True,
            },
            # RDS
            {
                "Id": "rds_cpu",
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/RDS", "MetricName": "CPUUtilization"},
                    "Period": selected_period,
                    "Stat": "Average",
                    "Unit": "Percent",
                },
                "ReturnData": True,
            },
            {
                "Id": "rds_connections",
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/RDS", "MetricName": "DatabaseConnections"},
                    "Period": selected_period,
                    "Stat": "Average",
                    "Unit": "Count",
                },
                "ReturnData": True,
            },
            {
                "Id": "rds_free_storage",
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/RDS", "MetricName": "FreeStorageSpace"},
                    "Period": selected_period,
                    "Stat": "Average",
                    "Unit": "Bytes",
                },
                "ReturnData": True,
            },
            {
                "Id": "rds_free_memory",
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/RDS", "MetricName": "FreeableMemory"},
                    "Period": selected_period,
                    "Stat": "Average",
                    "Unit": "Bytes",
                },
                "ReturnData": True,
            },
            # ScamShield Operations
            {
                "Id": "ops_reports_submitted",
                "MetricStat": {
                    "Metric": {"Namespace": "ScamShield/Operations", "MetricName": "ReportsSubmitted"},
                    "Period": selected_period,
                    "Stat": "Sum",
                    "Unit": "Count",
                },
                "ReturnData": True,
            },
            {
                "Id": "ops_reports_high_priority",
                "MetricStat": {
                    "Metric": {"Namespace": "ScamShield/Operations", "MetricName": "ReportsHighPriority"},
                    "Period": selected_period,
                    "Stat": "Sum",
                    "Unit": "Count",
                },
                "ReturnData": True,
            },
            {
                "Id": "ops_alerts_published",
                "MetricStat": {
                    "Metric": {"Namespace": "ScamShield/Operations", "MetricName": "AlertsPublished"},
                    "Period": selected_period,
                    "Stat": "Sum",
                    "Unit": "Count",
                },
                "ReturnData": True,
            },
            {
                "Id": "ops_rate_limit_blocks",
                "MetricStat": {
                    "Metric": {"Namespace": "ScamShield/Operations", "MetricName": "RateLimitBlocks"},
                    "Period": selected_period,
                    "Stat": "Sum",
                    "Unit": "Count",
                },
                "ReturnData": True,
            },
            {
                "Id": "ops_scan_failures",
                "MetricStat": {
                    "Metric": {"Namespace": "ScamShield/Operations", "MetricName": "ScanFailures"},
                    "Period": selected_period,
                    "Stat": "Sum",
                    "Unit": "Count",
                },
                "ReturnData": True,
            },
            {
                "Id": "ops_login_failures",
                "MetricStat": {
                    "Metric": {"Namespace": "ScamShield/Operations", "MetricName": "LoginFailures"},
                    "Period": selected_period,
                    "Stat": "Sum",
                    "Unit": "Count",
                },
                "ReturnData": True,
            },
        ]

        cw = client("cloudwatch")
        response = cw.get_metric_data(
            MetricDataQueries=queries,
            StartTime=start_time,
            EndTime=now,
        )

        results_by_id = {}
        for r in response.get("MetricDataResults", []):
            qid = r.get("Id")
            timestamps = r.get("Timestamps", [])
            values = r.get("Values", [])
            series = [
                {"timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts), "value": float(v)}
                for ts, v in zip(timestamps, values, strict=False)
            ]
            series.sort(key=lambda x: x["timestamp"])
            results_by_id[qid] = series

        response_data = {
            "time_range": time_range,
            "period": selected_period,
            "generated_at": now.isoformat(),
            "degraded": False,
            "infrastructure": {
                "ec2": {"cpu": results_by_id.get("ec2_cpu", [])},
                "alb": {
                    "5xx": results_by_id.get("alb_5xx", []),
                    "latency": results_by_id.get("alb_latency", []),
                    "healthy_hosts": results_by_id.get("alb_healthy_hosts", []),
                },
                "rds": {
                    "cpu": results_by_id.get("rds_cpu", []),
                    "connections": results_by_id.get("rds_connections", []),
                    "free_storage": results_by_id.get("rds_free_storage", []),
                    "free_memory": results_by_id.get("rds_free_memory", []),
                },
            },
            "operations": {
                "reports_submitted": results_by_id.get("ops_reports_submitted", []),
                "reports_high_priority": results_by_id.get("ops_reports_high_priority", []),
                "alerts_published": results_by_id.get("ops_alerts_published", []),
                "rate_limit_blocks": results_by_id.get("ops_rate_limit_blocks", []),
                "scan_failures": results_by_id.get("ops_scan_failures", []),
                "login_failures": results_by_id.get("ops_login_failures", []),
            },
        }

        cache.set(cache_key, response_data, timeout=60)
        return response_data
    except Exception as exc:
        logger.warning("Failed to fetch CloudWatch dashboard series: %s", exc)
        return degraded_response
