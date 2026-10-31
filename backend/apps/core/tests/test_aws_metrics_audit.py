from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from django.test import override_settings

from apps.core.audit import log_event
from apps.core.aws import client as get_aws_client
from apps.core.aws import reset_clients
from apps.core.logging import FORBIDDEN_PII_KEYS, set_correlation_id
from apps.core.metrics import emit as emit_metric
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog


class TestAwsClientFactory:
    """Verify core.aws client factory configuration, timeouts, and caching (D31 / §3.4)."""

    def setup_method(self):
        reset_clients()

    def teardown_method(self):
        reset_clients()

    def test_client_is_cached(self):
        c1 = get_aws_client("s3")
        c2 = get_aws_client("s3")
        assert c1 is c2

    def test_reset_clients_clears_cache(self):
        c1 = get_aws_client("s3")
        reset_clients()
        c2 = get_aws_client("s3")
        assert c1 is not c2

    def test_client_timeouts_configured(self):
        c = get_aws_client("cloudwatch")
        config = c.meta.config
        assert config.connect_timeout == 2
        assert config.read_timeout == 5
        assert config.retries.get("total_max_attempts") == 3 or config.retries.get("max_attempts") == 2


class TestMetricsEmitter:
    """Verify CloudWatch metrics emitter behavior and failure safety (D32 / §3.2)."""

    @override_settings(METRICS_ENABLED=False)
    def test_emit_disabled_does_not_call_aws(self):
        mock_cw = MagicMock()
        with patch("apps.core.metrics.client", return_value=mock_cw):
            emit_metric("ReportsSubmitted", value=1)
            mock_cw.put_metric_data.assert_not_called()

    @override_settings(METRICS_ENABLED=True)
    def test_emit_enabled_calls_put_metric_data(self):
        mock_cw = MagicMock()
        with patch("apps.core.metrics.client", return_value=mock_cw):
            emit_metric("ReportsSubmitted", value=2, unit="Count", dims={"Environment": "test", "InvalidDim": "drop_me"})

            mock_cw.put_metric_data.assert_called_once()
            call_kwargs = mock_cw.put_metric_data.call_args[1]
            assert call_kwargs["Namespace"] == "ScamShield/Operations"
            metric = call_kwargs["MetricData"][0]
            assert metric["MetricName"] == "ReportsSubmitted"
            assert metric["Value"] == 2
            assert metric["Unit"] == "Count"
            # Only allowed dimensions passed
            dim_names = {d["Name"] for d in metric["Dimensions"]}
            assert dim_names == {"Environment"}

    @override_settings(METRICS_ENABLED=True)
    def test_emit_never_raises_on_aws_error(self):
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "PutMetricData",
        )
        with patch("apps.core.metrics.client", return_value=mock_cw):
            # Must not raise
            emit_metric("ReportsSubmitted", value=1)


class TestAuditWriter:
    """Verify append-only audit logger, PII refusal, and validation (D33 / §3.1)."""

    @pytest.mark.django_db
    def test_log_event_creates_record(self):
        log = log_event(
            AuditEventType.REPORT_SUBMITTED,
            severity=AuditSeverity.INFO,
            metadata={"source": "api"},
            request_id="req-audit-123",
        )
        assert isinstance(log, SystemAuditLog)
        assert log.event_type == AuditEventType.REPORT_SUBMITTED
        assert log.severity == AuditSeverity.INFO
        assert log.metadata == {"source": "api"}
        assert log.request_id == "req-audit-123"
        assert log.target_type == ""
        assert log.target_id == ""

    @pytest.mark.django_db
    def test_log_event_uses_correlation_id_contextvar_when_none(self):
        set_correlation_id("req-ctx-999")
        try:
            log = log_event(
                AuditEventType.LOGIN_SUCCESS,
                severity=AuditSeverity.INFO,
            )
            assert log.request_id == "req-ctx-999"
        finally:
            set_correlation_id("")

    @pytest.mark.django_db
    def test_log_event_invalid_event_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid event_type"):
            log_event("INVALID_NONEXISTENT_EVENT_TYPE")

    @pytest.mark.django_db
    def test_log_event_invalid_severity_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid severity"):
            log_event(AuditEventType.REPORT_SUBMITTED, severity="SUPER_CRITICAL_UNKNOWN")

    @pytest.mark.django_db
    @pytest.mark.parametrize("pii_key", sorted(FORBIDDEN_PII_KEYS))
    def test_log_event_raises_on_forbidden_pii_key(self, pii_key: str):
        with pytest.raises(ValueError, match="PII key"):
            log_event(
                AuditEventType.REPORT_SUBMITTED,
                metadata={pii_key: "leaked_secret_val"},
            )
