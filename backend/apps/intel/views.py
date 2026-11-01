from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole
from apps.core.ip import client_ip_hash
from apps.core.pagination import StandardPagination
from apps.intel.models import IndicatorStatus, IndicatorType, ThreatLevel, VerifiedIndicator
from apps.intel.selectors.triage_selectors import get_report_detail, get_triage_queue_queryset
from apps.intel.serializers import (
    CurateIndicatorRequestSerializer,
    EvidencePresignedResponseSerializer,
    QueueReportSerializer,
    RejectReportRequestSerializer,
    RejectReportResponseSerializer,
    ReportDetailSerializer,
    RevokeIndicatorRequestSerializer,
    VerifiedIndicatorSerializer,
    VerifyReportRequestSerializer,
    VerifyReportResponseSerializer,
)
from apps.intel.services.evidence_service import issue_evidence_presigned_urls
from apps.intel.services.triage_service import (
    curate_indicator,
    reject_report,
    revoke_indicator,
    verify_indicator,
)
from apps.reports.models import Platform, ScamCategory, ScamReport


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


class TriageEvidenceView(APIView):
    """
    GET /api/v1/triage/reports/{id}/evidence/
    Returns temporary S3 pre-signed download URLs for clean evidence files.
    Strictly restricted to approved analysts.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST)]

    @extend_schema(
        summary="Get evidence presigned URLs",
        description="Returns temporary S3 pre-signed get_object URLs (ExpiresIn=900, attachment) for clean evidence files.",
        responses={200: EvidencePresignedResponseSerializer(many=True)},
    )
    def get(self, request, id, *args, **kwargs):
        report = get_object_or_404(ScamReport, id=id)
        ip_hash = client_ip_hash(request)
        urls = issue_evidence_presigned_urls(report=report, actor=request.user, ip_hash=ip_hash)
        return Response(urls, status=200)


class TriageRejectReportView(APIView):
    """
    POST /api/v1/triage/reports/{id}/reject/
    Rejects a pending report with a mandatory reason.
    Strictly restricted to approved analysts.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST)]

    @extend_schema(
        summary="Reject report",
        description="Rejects a pending report with a mandatory non-blank reason (max 500 chars).",
        request=RejectReportRequestSerializer,
        responses={200: RejectReportResponseSerializer},
    )
    def post(self, request, id, *args, **kwargs):
        serializer = RejectReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]
        ip_hash = client_ip_hash(request)
        report = reject_report(report_id=id, analyst=request.user, reason=reason, ip_hash=ip_hash)
        return Response(
            {
                "id": str(report.id),
                "status": report.status,
                "reference_code": report.reference_code,
            },
            status=200,
        )


class TriageVerifyReportView(APIView):
    """
    POST /api/v1/triage/reports/{id}/verify/
    Verifies a cluster of pending scam reports sharing the target indicator.
    Strictly restricted to approved analysts.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST)]

    @extend_schema(
        summary="Verify report indicator cluster",
        description="Verifies a cluster of pending reports sharing an indicator, promotes to VerifiedIndicator, and resolves all reports in the cluster.",
        request=VerifyReportRequestSerializer,
        responses={200: VerifyReportResponseSerializer},
    )
    def post(self, request, id, *args, **kwargs):
        serializer = VerifyReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report_indicator_id = serializer.validated_data["report_indicator_id"]
        public_note = serializer.validated_data.get("public_note", "")
        ip_hash = client_ip_hash(request)
        result = verify_indicator(
            analyst=request.user,
            report_id=id,
            report_indicator_id=report_indicator_id,
            public_note=public_note,
            ip_hash=ip_hash,
        )
        response_serializer = VerifyReportResponseSerializer(result)
        return Response(response_serializer.data, status=200)


class TriageIndicatorsListView(generics.ListAPIView):
    """
    GET /api/v1/triage/indicators/
    Returns verified indicators with filtering and search.
    Accessible to ANALYST and ADMIN.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST, Role.ADMIN)]
    serializer_class = VerifiedIndicatorSerializer
    pagination_class = StandardPagination

    @extend_schema(
        summary="List verified indicators",
        description="Returns verified indicators with filtering by type, threat_level, status, and search.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            VerifiedIndicator.objects.select_related("verified_by", "revoked_by")
            .order_by("-last_seen_at", "-total_report_count", "id")
        )
        params = self.request.query_params

        # Filter: type
        itype = params.get("type")
        if itype:
            if itype not in IndicatorType.values:
                raise serializers.ValidationError(
                    {"type": [f"Invalid indicator type '{itype}'."]},
                    code="validation_error",
                )
            qs = qs.filter(type=itype)

        # Filter: threat_level
        threat_level = params.get("threat_level")
        if threat_level:
            if threat_level not in ThreatLevel.values:
                raise serializers.ValidationError(
                    {"threat_level": [f"Invalid threat level '{threat_level}'."]},
                    code="validation_error",
                )
            qs = qs.filter(threat_level=threat_level)

        # Filter: status
        status = params.get("status")
        if status:
            if status not in IndicatorStatus.values:
                raise serializers.ValidationError(
                    {"status": [f"Invalid status '{status}'."]},
                    code="validation_error",
                )
            qs = qs.filter(status=status)

        # Filter: search
        search = params.get("search")
        if search:
            search = search.strip()
            if search:
                qs = qs.filter(
                    Q(normalized_value__icontains=search)
                    | Q(public_note__icontains=search)
                )

        return qs


class TriageIndicatorDetailView(APIView):
    """
    GET /api/v1/triage/indicators/{id}/
    PATCH /api/v1/triage/indicators/{id}/
    Detail view (ANALYST, ADMIN) and curation endpoint (ANALYST only).
    """

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAuthenticated(), HasRole(Role.ANALYST)()]
        return [IsAuthenticated(), HasRole(Role.ANALYST, Role.ADMIN)()]

    @extend_schema(
        summary="Retrieve verified indicator detail",
        description="Returns full VerifiedIndicator details. Accessible to ANALYST and ADMIN.",
        responses={200: VerifiedIndicatorSerializer},
    )
    def get(self, request, id, *args, **kwargs):
        indicator = get_object_or_404(
            VerifiedIndicator.objects.select_related("verified_by", "revoked_by"),
            id=id,
        )
        return Response(VerifiedIndicatorSerializer(indicator).data)

    @extend_schema(
        summary="Curate verified indicator public note",
        description="Updates public_note on a verified indicator. Restricted to ANALYST.",
        request=CurateIndicatorRequestSerializer,
        responses={200: VerifiedIndicatorSerializer},
    )
    def patch(self, request, id, *args, **kwargs):
        indicator = get_object_or_404(VerifiedIndicator, id=id)
        serializer = CurateIndicatorRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_note = serializer.validated_data.get("public_note", indicator.public_note)
        updated = curate_indicator(indicator_id=indicator.id, public_note=new_note)
        return Response(VerifiedIndicatorSerializer(updated).data, status=200)


class TriageIndicatorRevokeView(APIView):
    """
    POST /api/v1/triage/indicators/{id}/revoke/
    Revokes an active indicator. Restricted to ANALYST.
    """

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST)]

    @extend_schema(
        summary="Revoke verified indicator",
        description="Revokes an active verified indicator with a required reason. Restricted to ANALYST.",
        request=RevokeIndicatorRequestSerializer,
        responses={200: VerifiedIndicatorSerializer},
    )
    def post(self, request, id, *args, **kwargs):
        serializer = RevokeIndicatorRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]
        ip_hash = client_ip_hash(request)
        indicator = revoke_indicator(
            indicator_id=id,
            analyst=request.user,
            reason=reason,
            ip_hash=ip_hash,
        )
        return Response(VerifiedIndicatorSerializer(indicator).data, status=200)
