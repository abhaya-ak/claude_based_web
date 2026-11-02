from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from django.core.cache import cache
from django.test import override_settings
from moto import mock_aws

from apps.core.aws import client as get_aws_client
from apps.ops.services.cloudwatch_service import get_dashboard_series, put_metrics


@pytest.fixture(autouse=True)
def clear_telemetry_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestCloudWatchService:
    @mock_aws
    @override_settings(METRICS_ENABLED=True)
    def test_put_metrics_batching_under_moto(self):
        """Prove put_metrics batches > 20 datums into chunks of at most 20."""
        cw = get_aws_client("cloudwatch")
        with patch.object(cw, "put_metric_data", wraps=cw.put_metric_data) as spy_put:
            items = [
                {
                    "name": "ReportsSubmitted",
                    "value": float(i),
                    "unit": "Count",
                    "dims": {"Environment": "test"},
                }
                for i in range(45)
            ]
            success = put_metrics(items)
            assert success is True
            # 45 items batched in chunks of 20 -> 3 calls (20, 20, 5)
            assert spy_put.call_count == 3
            assert len(spy_put.call_args_list[0][1]["MetricData"]) == 20
            assert len(spy_put.call_args_list[1][1]["MetricData"]) == 20
            assert len(spy_put.call_args_list[2][1]["MetricData"]) == 5

    @override_settings(METRICS_ENABLED=True)
    def test_to_be_proven_22_put_metrics_and_get_dashboard_series_never_raise_on_error(self):
        """TO BE PROVEN #22: CloudWatch calls never raise unhandled exceptions on error."""
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "InternalServiceError", "Message": "CloudWatch is down"}},
            "PutMetricData",
        )
        mock_cw.get_metric_data.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "GetMetricData",
        )

        with patch("apps.ops.services.cloudwatch_service.client", return_value=mock_cw):
            # put_metrics should catch and return False without raising
            put_res = put_metrics([{"name": "ReportsSubmitted", "value": 1.0}])
            assert put_res is False

            # get_dashboard_series should catch and return degraded structure without raising
            data = get_dashboard_series(time_range="24h")
            assert isinstance(data, dict)
            assert data["degraded"] is True
            assert data["time_range"] == "24h"
            assert data["infrastructure"]["ec2"]["cpu"] == []
            assert data["operations"]["reports_submitted"] == []

    @mock_aws
    @override_settings(METRICS_ENABLED=True)
    def test_to_be_proven_22_get_dashboard_series_caching(self):
        """TO BE PROVEN #22: Second call within 60s hits cache with 0 extra AWS API calls."""
        mock_cw = MagicMock()
        mock_cw.get_metric_data.return_value = {
            "MetricDataResults": [
                {
                    "Id": "ec2_cpu",
                    "Timestamps": [datetime(2026, 11, 2, 12, 0, tzinfo=UTC)],
                    "Values": [15.5],
                }
            ]
        }

        with patch("apps.ops.services.cloudwatch_service.client", return_value=mock_cw):
            first = get_dashboard_series(time_range="24h")
            assert mock_cw.get_metric_data.call_count == 1
            assert first["degraded"] is False
            assert len(first["infrastructure"]["ec2"]["cpu"]) == 1

            # Second call immediately should hit Django cache
            second = get_dashboard_series(time_range="24h")
            assert mock_cw.get_metric_data.call_count == 1  # No second call
            assert second == first

    def test_get_dashboard_series_time_ranges_validation(self):
        """Test valid time ranges and invalid time range rejection."""
        with pytest.raises(ValueError, match="Invalid time_range"):
            get_dashboard_series(time_range="99d")

    @mock_aws
    @override_settings(METRICS_ENABLED=True)
    def test_get_dashboard_series_under_moto(self):
        """Under Moto, get_dashboard_series returns properly formatted series data."""
        data = get_dashboard_series(time_range="1h")
        assert data["degraded"] is False
        assert data["time_range"] == "1h"
        assert data["period"] == 60
        assert "ec2" in data["infrastructure"]
        assert "alb" in data["infrastructure"]
        assert "rds" in data["infrastructure"]
        assert "reports_submitted" in data["operations"]
        assert "alerts_published" in data["operations"]
