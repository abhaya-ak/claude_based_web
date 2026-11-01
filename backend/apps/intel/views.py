from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole
from apps.core.pagination import StandardPagination
from apps.intel.selectors.triage_selectors import get_report_detail, get_triage_queue_queryset
from apps.intel.serializers import QueueReportSerializer, ReportDetailSerializer
from apps.reports.models import Platform, ScamCategory


class TriageQueueView(generics.ListAPIView):
    """
    GET /api/v1/triage/queue/
    Returns pending scam reports for analyst triage, annotated with cluster_size,
    ordered by risk_score DESC NULLS LAST, cluster_size DESC, created_at ASC, id ASC.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST, Role.ADMIN)]
    serializer_class = QueueReportSerializer
    pagination_class = StandardPagination

    @extend_schema(
        summary="List triage queue",
        description="Returns pending scam reports annotated with cluster_size.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = get_triage_queue_queryset()
        params = self.request.query_params

        # Filter: platform
        platform = params.get("platform")
        if platform:
            if platform not in Platform.values:
                raise serializers.ValidationError(
                    {"platform": [f"Invalid platform '{platform}'. Must be one of {Platform.values}."]}
                )
            qs = qs.filter(platform=platform)

        # Filter: category
        category = params.get("category")
        if category:
            if category not in ScamCategory.values:
                raise serializers.ValidationError(
                    {"category": [f"Invalid category '{category}'. Must be one of {ScamCategory.values}."]}
                )
            qs = qs.filter(category=category)

        # Filter: is_high_priority
        is_hp = params.get("is_high_priority")
        if is_hp is not None:
            lower = is_hp.lower().strip()
            if lower in ("true", "1"):
                qs = qs.filter(is_high_priority=True)
            elif lower in ("false", "0"):
                qs = qs.filter(is_high_priority=False)
            else:
                raise serializers.ValidationError(
                    {"is_high_priority": ["Must be a valid boolean ('true' or 'false')."]}
                )

        # Filter: min_risk_score
        min_score = params.get("min_risk_score")
        if min_score is not None:
            try:
                score_val = int(min_score)
                if not (0 <= score_val <= 100):
                    raise ValueError()
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    {"min_risk_score": ["Must be an integer between 0 and 100."]}
                ) from None
            qs = qs.filter(risk_score__gte=score_val)

        return qs


class TriageReportDetailView(APIView):
    """
    GET /api/v1/triage/reports/{id}/
    Returns full analyst detail view of a scam report including raw indicators,
    victim narrative, scan breakdown, evidence files metadata, and cluster size.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST, Role.ADMIN)]

    @extend_schema(
        summary="Get triage report detail",
        description="Returns full analyst detail for a scam report.",
        responses={200: ReportDetailSerializer},
    )
    def get(self, request, id, *args, **kwargs):
        report = get_report_detail(id)
        serializer = ReportDetailSerializer(report)
        return Response(serializer.data)
