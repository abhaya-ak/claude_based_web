import csv
import io
from typing import Any

from django.http import StreamingHttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole
from apps.core.pagination import StandardPagination
from apps.ops.selectors.audit_selectors import filter_audit_logs
from apps.ops.serializers import (
    SystemAuditLogSerializer,
    TelemetryQuerySerializer,
    TelemetryResponseSerializer,
)
from apps.ops.services import cloudwatch_service


def _sanitize_csv_cell(val: Any) -> str:
    """Neutralizes CSV formula injection vulnerabilities."""
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


def _generate_audit_log_csv(queryset):
    """Streaming CSV generator capped at 5,000 rows."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    headers = [
        "id",
        "occurred_at",
        "event_type",
        "severity",
        "actor_id",
        "actor_role",
        "actor_ip_hash",
        "target_type",
        "target_id",
        "request_id",
    ]
    writer.writerow(headers)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for item in queryset[:5000].iterator(chunk_size=500):
        actor_role = item.actor.role if item.actor_id and item.actor else ""
        row = [
            _sanitize_csv_cell(item.id),
            _sanitize_csv_cell(item.occurred_at.isoformat() if hasattr(item.occurred_at, "isoformat") else item.occurred_at),
            _sanitize_csv_cell(item.event_type),
            _sanitize_csv_cell(item.severity),
            _sanitize_csv_cell(item.actor_id),
            _sanitize_csv_cell(actor_role),
            _sanitize_csv_cell(item.actor_ip_hash),
            _sanitize_csv_cell(item.target_type),
            _sanitize_csv_cell(item.target_id),
            _sanitize_csv_cell(item.request_id),
        ]
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


class TelemetryMetricsView(APIView):
    """
    Returns chart-ready CloudWatch metric series for infrastructure and operational health.
    Restricted strictly to approved ADMIN. Caches responses for 60 seconds.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]
    serializer_class = TelemetryResponseSerializer

    @extend_schema(
        summary="Get telemetry metrics series",
        parameters=[TelemetryQuerySerializer],
        responses={200: TelemetryResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        query_serializer = TelemetryQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        time_range = query_serializer.validated_data.get("range", "24h")

        data = cloudwatch_service.get_dashboard_series(time_range=time_range)

        response = Response(data, status=status.HTTP_200_OK)
        response["Cache-Control"] = "private, max-age=60"
        return response


class AdminAuditLogListView(generics.ListAPIView):
    """
    Paginated audit log viewer with filtering.
    Restricted strictly to approved ADMIN.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]
    serializer_class = SystemAuditLogSerializer
    pagination_class = StandardPagination

    @extend_schema(summary="List system audit logs")
    def get_queryset(self):
        qp = self.request.query_params
        return filter_audit_logs(
            event_type=qp.get("event_type"),
            severity=qp.get("severity"),
            date_from=qp.get("date_from"),
            date_to=qp.get("date_to"),
            actor_id=qp.get("actor_id"),
            ip_hash=qp.get("ip_hash"),
        )


class AdminAuditLogExportView(APIView):
    """
    Streams CSV export of system audit logs with active filters.
    Restricted strictly to approved ADMIN. Capped at 5,000 rows.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]

    @extend_schema(
        summary="Export system audit logs as CSV",
        responses={200: {"type": "string", "format": "binary"}},
    )
    def get(self, request, *args, **kwargs):
        qp = request.query_params
        qs = filter_audit_logs(
            event_type=qp.get("event_type"),
            severity=qp.get("severity"),
            date_from=qp.get("date_from"),
            date_to=qp.get("date_to"),
            actor_id=qp.get("actor_id"),
            ip_hash=qp.get("ip_hash"),
        )

        response = StreamingHttpResponse(
            _generate_audit_log_csv(qs),
            content_type="text/csv",
        )
        response["Content-Disposition"] = 'attachment; filename="audit_logs.csv"'
        return response
