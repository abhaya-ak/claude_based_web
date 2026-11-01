import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.ip import client_ip_hash
from apps.core.pagination import StandardPagination
from apps.reports.models import ScamReport
from apps.reports.selectors.report_selectors import get_report_options
from apps.reports.serializers import (
    MyReportItemSerializer,
    ReportCreateRequestSerializer,
    ReportCreateResponseSerializer,
    ReportOptionsResponseSerializer,
    ReportTrackRequestSerializer,
    ReportTrackResponseSerializer,
    validate_evidence_files,
)
from apps.reports.services.report_service import create_report, track_report


class ReportOptionsView(APIView):
    """
    Public options endpoint returning allowed countries, currencies,
    categories, platforms, payment methods, and admin areas per country.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Retrieve report submission options and allow-lists",
        description="Public endpoint returning enums and country-specific allow-lists.",
        responses={200: ReportOptionsResponseSerializer},
    )
    def get(self, request):
        data = get_report_options()
        return Response(data, status=status.HTTP_200_OK)


class ReportCreateView(APIView):
    """
    Public report submission endpoint supporting multipart evidence uploads.
    """

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        summary="File a scam report",
        description="Submits a citizen scam report with 1 to 5 indicators and up to 3 evidence files.",
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.HEADER,
                required=False,
                description="Optional idempotency key UUID to prevent duplicate submissions.",
            )
        ],
        request=ReportCreateRequestSerializer,
        responses={
            201: ReportCreateResponseSerializer,
            200: OpenApiResponse(
                response=ReportCreateResponseSerializer,
                description="Idempotent replay of previously submitted report.",
            ),
            400: OpenApiResponse(description="Validation error"),
            413: OpenApiResponse(description="Payload exceeds 16 MB limit"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
    )
    def post(self, request):
        # 1. Parse Idempotency-Key header if provided
        idempotency_raw = request.headers.get("Idempotency-Key") or request.META.get(
            "HTTP_IDEMPOTENCY_KEY"
        )
        client_submission_id = None
        if idempotency_raw:
            try:
                client_submission_id = uuid.UUID(idempotency_raw)
            except (ValueError, TypeError) as exc:
                raise ValidationError(
                    {"detail": "Invalid Idempotency-Key header. Must be a valid UUID."}
                ) from exc

        # 2. Extract and validate evidence files
        file_list = request.FILES.getlist("evidence")
        clean_file_bytes = validate_evidence_files(file_list)

        # 3. Validate form / body fields
        serializer = ReportCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        ip_hash = client_ip_hash(request)
        req_id = getattr(request, "correlation_id", None)
        user = request.user if getattr(request.user, "is_authenticated", False) else None

        # 4. Invoke service
        result = create_report(
            category=vd["category"],
            platform=vd["platform"],
            message_text=vd["message_text"],
            country_code=vd["country_code"],
            currency=vd["currency"],
            financial_loss=vd["financial_loss"],
            payment_method=vd["payment_method"],
            admin_area=vd.get("admin_area"),
            incident_date=vd.get("incident_date"),
            indicators=vd["indicators"],
            evidence_files=clean_file_bytes,
            client_submission_id=client_submission_id,
            anonymous=vd.get("anonymous", False),
            user=user,
            ip_hash=ip_hash,
            request_id=req_id,
        )

        response_data = {
            "reference_code": result.report.reference_code,
            "status": result.report.status,
            "access_key": result.access_key,
            "playbook": result.playbook,
        }

        resp_status = (
            status.HTTP_200_OK if result.is_replay else status.HTTP_201_CREATED
        )
        return Response(response_data, status=resp_status)


class ReportTrackView(APIView):
    """
    Public report status lookup endpoint using reference code and access key.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Track status of a filed report",
        description="Public tracking endpoint. Returns uniform 404 for unknown references and invalid keys.",
        request=ReportTrackRequestSerializer,
        responses={
            200: ReportTrackResponseSerializer,
            404: OpenApiResponse(description="Report not found"),
            429: OpenApiResponse(description="Too many failed tracking attempts"),
        },
    )
    def post(self, request):
        serializer = ReportTrackRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ref_code = serializer.validated_data["reference_code"]
        access_key = serializer.validated_data.get("access_key")
        ip_hash = client_ip_hash(request)

        report, playbook = track_report(
            reference_code=ref_code,
            access_key=access_key,
            user=request.user,
            ip_hash=ip_hash,
        )

        data = {
            "reference_code": report.reference_code,
            "status": report.status,
            "category": report.category,
            "platform": report.platform,
            "financial_loss": str(report.financial_loss),
            "currency": report.currency,
            "created_at": report.created_at,
            "playbook": playbook,
        }
        return Response(data, status=status.HTTP_200_OK)


class MyReportsView(generics.ListAPIView):
    """
    Authenticated list of non-anonymous reports submitted by the caller.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    serializer_class = MyReportItemSerializer

    @extend_schema(
        summary="List reports filed by authenticated user",
        description="Returns paginated reports filed by the caller. Anonymous reports are excluded.",
        responses={200: MyReportItemSerializer(many=True)},
    )
    def get_queryset(self):
        # D80: anonymous reports never appear in anyone's list
        # Query optimization avoids N+1 queries
        return (
            ScamReport.objects.filter(
                reporter=self.request.user,
                is_anonymous=False,
            )
            .order_by("-created_at")
            .only(
                "reference_code",
                "category",
                "platform",
                "status",
                "financial_loss",
                "currency",
                "created_at",
            )
        )
