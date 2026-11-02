from django.urls import path

from apps.ops.views import (
    AdminAuditLogExportView,
    AdminAuditLogListView,
    TelemetryMetricsView,
)

app_name = "ops"

urlpatterns = [
    path("telemetry/metrics/", TelemetryMetricsView.as_view(), name="admin-telemetry-metrics"),
    path("audit-logs/", AdminAuditLogListView.as_view(), name="admin-audit-logs-list"),
    path("audit-logs/export/", AdminAuditLogExportView.as_view(), name="admin-audit-logs-export"),
]
