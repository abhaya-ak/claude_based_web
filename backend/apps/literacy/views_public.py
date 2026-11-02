from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.core.enums import AudienceGroup
from apps.core.pagination import StandardPagination
from apps.literacy.models import ContentStatus, EducationalGuide
from apps.literacy.serializers import (
    EducationalGuidePublicDetailSerializer,
    EducationalGuidePublicListSerializer,
)


class PublicGuideListView(generics.ListAPIView):
    """
    Public hub endpoint listing published educational guides.
    Supports filtering by audience group, language, and tactic.
    Includes ui_hints tuned for target audience accessibility (e.g. ELDERLY).
    """

    permission_classes = [AllowAny]
    throttle_scope = "public_read"
    pagination_class = StandardPagination
    serializer_class = EducationalGuidePublicListSerializer

    def get_queryset(self):
        qs = (
            EducationalGuide.objects.filter(status=ContentStatus.PUBLISHED.value)
            .prefetch_related("assets")
            .order_by("-published_at")
        )

        group = self.request.query_params.get("group")
        if group:
            qs = qs.filter(audience_groups__contains=[group])

        language = self.request.query_params.get("language")
        if language:
            qs = qs.filter(language=language)

        tactic = self.request.query_params.get("tactic")
        if tactic:
            qs = qs.filter(tactics__contains=[tactic])

        return qs

    @extend_schema(
        summary="List published educational guides",
        parameters=[
            OpenApiParameter(
                name="group",
                description="Filter by target audience group (e.g. GENERAL, ELDERLY, YOUTH)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="language",
                description="Filter by language code (e.g. en, ne, ms)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="tactic",
                description="Filter by scam tactic (e.g. URGENCY, AUTHORITY, FEAR, GREED)",
                required=False,
                type=str,
            ),
        ],
        responses={200: EducationalGuidePublicListSerializer},
    )
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        group = request.query_params.get("group")
        if group == AudienceGroup.ELDERLY.value:
            ui_hints = {"base_font_px": 20, "high_contrast": True, "tts": True}
        else:
            ui_hints = {"base_font_px": 16, "high_contrast": False, "tts": False}

        if isinstance(response.data, dict):
            response.data["ui_hints"] = ui_hints
        return response


class PublicGuideDetailView(generics.RetrieveAPIView):
    """
    Public detail endpoint retrieving a published guide by unique slug.
    Prefetches media assets and provides sanitized markdown body text.
    Returns 404 for draft or archived guides.
    """

    permission_classes = [AllowAny]
    throttle_scope = "public_read"
    lookup_field = "slug"
    serializer_class = EducationalGuidePublicDetailSerializer

    def get_queryset(self):
        return (
            EducationalGuide.objects.filter(status=ContentStatus.PUBLISHED.value)
            .prefetch_related("assets")
        )

    @extend_schema(
        summary="Retrieve published educational guide by slug",
        responses={200: EducationalGuidePublicDetailSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
