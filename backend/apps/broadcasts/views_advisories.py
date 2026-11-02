from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import ApprovalStatus, Role
from apps.accounts.permissions import HasRole
from apps.broadcasts.models import AdvisoryStatus, ThreatAdvisory
from apps.broadcasts.serializers import (
    ThreatAdvisoryCreateSerializer,
    ThreatAdvisoryPublicSerializer,
    ThreatAdvisoryStaffSerializer,
    ThreatAdvisoryUpdateSerializer,
)
from apps.broadcasts.services.broadcast_service import publish_advisory
from apps.core.exceptions import ConflictError
from apps.core.pagination import StandardPagination


def _is_staff_user(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "approval_status", None) == ApprovalStatus.APPROVED
        and getattr(user, "role", None) in {Role.ANALYST, Role.ADMIN}
    )


class AdvisoryListCreateView(generics.ListCreateAPIView):
    """Public list of published advisories; staff creation and workbench filtering per D109."""

    throttle_scope = "public_read"
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), HasRole(Role.ANALYST)]
        return [AllowAny()]

    def get_queryset(self):
        user = self.request.user
        if _is_staff_user(user):
            qs = ThreatAdvisory.objects.all()
            status_param = self.request.query_params.get("status")
            if status_param:
                qs = qs.filter(status=status_param)
        else:
            qs = ThreatAdvisory.objects.filter(status=AdvisoryStatus.PUBLISHED)

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        severity = self.request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)

        target_audience = self.request.query_params.get("target_audience")
        if target_audience:
            qs = qs.filter(target_audience=target_audience)

        return qs.order_by("-published_at", "-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ThreatAdvisoryCreateSerializer
        return ThreatAdvisoryStaffSerializer if _is_staff_user(self.request.user) else ThreatAdvisoryPublicSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name="status", description="Filter by status (Staff only)", required=False, type=str),
            OpenApiParameter(name="category", description="Filter by scam category", required=False, type=str),
            OpenApiParameter(name="severity", description="Filter by severity", required=False, type=str),
            OpenApiParameter(name="target_audience", description="Filter by target audience", required=False, type=str),
        ],
        responses={200: ThreatAdvisoryPublicSerializer(many=True)},
        description="Public list of published threat advisories; workbench filtering for approved staff.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=ThreatAdvisoryCreateSerializer,
        responses={201: ThreatAdvisoryStaffSerializer},
        description="Create a new threat advisory in DRAFT status (Analyst only).",
    )
    def post(self, request, *args, **kwargs):
        serializer = ThreatAdvisoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vdata = serializer.validated_data

        advisory = ThreatAdvisory.objects.create(
            title=vdata["title"],
            body=vdata["body"],
            sms_text=vdata.get("sms_text"),
            severity=vdata["severity"],
            target_audience=vdata["target_audience"],
            category=vdata.get("category"),
            related_indicator_id=vdata.get("related_indicator_id"),
            status=AdvisoryStatus.DRAFT,
            created_by=request.user,
        )
        return Response(ThreatAdvisoryStaffSerializer(advisory).data, status=status.HTTP_201_CREATED)


class AdvisoryDetailView(APIView):
    """Public detail of published advisory; draft-only patch restricted to approved Analyst per D109."""

    throttle_scope = "public_read"

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT"]:
            return [IsAuthenticated(), HasRole(Role.ANALYST)]
        return [AllowAny()]

    @extend_schema(
        responses={200: ThreatAdvisoryPublicSerializer},
        description="Get threat advisory detail (public if published, staff for any status).",
    )
    def get(self, request, pk, *args, **kwargs):
        advisory = get_object_or_404(ThreatAdvisory, id=pk)
        is_staff = _is_staff_user(request.user)

        if not is_staff and advisory.status != AdvisoryStatus.PUBLISHED:
            raise Http404("Advisory not found.")

        serializer = ThreatAdvisoryStaffSerializer(advisory) if is_staff else ThreatAdvisoryPublicSerializer(advisory)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=ThreatAdvisoryUpdateSerializer,
        responses={200: ThreatAdvisoryStaffSerializer},
        description="Update a threat advisory in DRAFT status only (Analyst only).",
    )
    def patch(self, request, pk, *args, **kwargs):
        with transaction.atomic():
            advisory = ThreatAdvisory.objects.select_for_update().filter(id=pk).first()
            if not advisory:
                raise Http404("Advisory not found.")

            if advisory.status != AdvisoryStatus.DRAFT:
                raise ConflictError(
                    detail="Only DRAFT advisories can be edited.",
                    code="advisory_not_draft",
                )

            serializer = ThreatAdvisoryUpdateSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            for key, value in serializer.validated_data.items():
                setattr(advisory, key, value)
            advisory.save()

            return Response(ThreatAdvisoryStaffSerializer(advisory).data, status=status.HTTP_200_OK)



class AdvisoryPublishView(APIView):
    """Publishes a threat advisory to the SNS alerts topic (Analyst only) per D110."""

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST)]

    @extend_schema(
        request=None,
        responses={200: ThreatAdvisoryStaffSerializer},
        description="Publish a threat advisory to the SNS alerts topic (Analyst only).",
    )
    def post(self, request, pk, *args, **kwargs):
        advisory = publish_advisory(pk, request.user)
        return Response(ThreatAdvisoryStaffSerializer(advisory).data, status=status.HTTP_200_OK)
