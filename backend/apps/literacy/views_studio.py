from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.core.pagination import StandardPagination
from apps.literacy.models import EducationalGuide
from apps.literacy.permissions import IsEducatorOrAdmin, IsGuideAuthorOrAdmin
from apps.literacy.serializers import (
    EducationalGuideCreateUpdateSerializer,
    EducationalGuideStudioSerializer,
)
from apps.literacy.services import guide_service


class StudioGuideListCreateView(generics.ListCreateAPIView):
    """
    Studio endpoint for creating and listing educational guides.
    EDUCATOR sees only their own guides; ADMIN sees all guides.
    Supports filtering by ?status=DRAFT|PUBLISHED|ARCHIVED.
    """

    permission_classes = [IsEducatorOrAdmin]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "role", None) == Role.ADMIN:
            qs = EducationalGuide.objects.all()
        else:
            qs = EducationalGuide.objects.filter(author=user)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        return qs.select_related("author").prefetch_related("assets").order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return EducationalGuideCreateUpdateSerializer
        return EducationalGuideStudioSerializer

    @extend_schema(
        summary="Create educational guide draft",
        request=EducationalGuideCreateUpdateSerializer,
        responses={201: EducationalGuideStudioSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guide = guide_service.create_guide(serializer.validated_data, author=request.user)
        out_serializer = EducationalGuideStudioSerializer(guide, context={"request": request})
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class StudioGuideDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Studio endpoint to retrieve, update, or delete a guide.
    EDUCATOR can only manage their own guides; ADMIN can manage any guide.
    Deleting is strictly allowed on DRAFT status only; returns 409 Conflict otherwise.
    """

    permission_classes = [IsGuideAuthorOrAdmin]
    lookup_field = "pk"

    def get_queryset(self):
        return EducationalGuide.objects.select_related("author").prefetch_related("assets")

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return EducationalGuideCreateUpdateSerializer
        return EducationalGuideStudioSerializer

    @extend_schema(
        summary="Update educational guide",
        request=EducationalGuideCreateUpdateSerializer,
        responses={200: EducationalGuideStudioSerializer},
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_guide = guide_service.update_guide(instance, serializer.validated_data)
        out_serializer = EducationalGuideStudioSerializer(updated_guide, context={"request": request})
        return Response(out_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Delete educational guide (draft only)",
        responses={204: None, 409: None},
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        guide_service.delete_guide(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudioGuidePublishView(APIView):
    """Publishes a guide, ensuring audience_groups >= 1 and preserving published_at."""

    permission_classes = [IsGuideAuthorOrAdmin]
    serializer_class = EducationalGuideStudioSerializer

    @extend_schema(
        summary="Publish educational guide",
        request=None,
        responses={200: EducationalGuideStudioSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        guide = get_object_or_404(
            EducationalGuide.objects.select_related("author").prefetch_related("assets"),
            pk=pk,
        )
        self.check_object_permissions(request, guide)
        published_guide = guide_service.publish_guide(guide)
        serializer = EducationalGuideStudioSerializer(published_guide, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudioGuideUnpublishView(APIView):
    """Reverts a guide back to DRAFT status."""

    permission_classes = [IsGuideAuthorOrAdmin]
    serializer_class = EducationalGuideStudioSerializer

    @extend_schema(
        summary="Unpublish educational guide",
        request=None,
        responses={200: EducationalGuideStudioSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        guide = get_object_or_404(
            EducationalGuide.objects.select_related("author").prefetch_related("assets"),
            pk=pk,
        )
        self.check_object_permissions(request, guide)
        unpublished_guide = guide_service.unpublish_guide(guide)
        serializer = EducationalGuideStudioSerializer(unpublished_guide, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudioGuideArchiveView(APIView):
    """Transitions a guide to ARCHIVED status."""

    permission_classes = [IsGuideAuthorOrAdmin]
    serializer_class = EducationalGuideStudioSerializer

    @extend_schema(
        summary="Archive educational guide",
        request=None,
        responses={200: EducationalGuideStudioSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        guide = get_object_or_404(
            EducationalGuide.objects.select_related("author").prefetch_related("assets"),
            pk=pk,
        )
        self.check_object_permissions(request, guide)
        archived_guide = guide_service.archive_guide(guide)
        serializer = EducationalGuideStudioSerializer(archived_guide, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
