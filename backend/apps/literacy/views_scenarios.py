from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.core.pagination import StandardPagination
from apps.literacy.models import ScenarioRedFlag, SimulatorScenario
from apps.literacy.permissions import IsEducatorOrAdmin, IsScenarioAuthorOrAdmin
from apps.literacy.serializers_scenario import (
    ScenarioRedFlagCreateSerializer,
    ScenarioRedFlagSerializer,
    StudioScenarioCreateSerializer,
    StudioScenarioSerializer,
    StudioScenarioUpdateSerializer,
)
from apps.literacy.services import simulator_service


class StudioScenarioListCreateView(generics.ListCreateAPIView):
    """
    Studio scenario list & create endpoint.
    EDUCATOR sees their own scenarios; ADMIN sees all scenarios.
    Supports filtering by ?status=, ?difficulty=, ?channel=, ?is_scam=.
    """

    permission_classes = [IsEducatorOrAdmin]
    pagination_class = StandardPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "role", None) == Role.ADMIN:
            qs = SimulatorScenario.objects.all()
        else:
            qs = SimulatorScenario.objects.filter(author=user)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        difficulty_param = self.request.query_params.get("difficulty")
        if difficulty_param:
            qs = qs.filter(difficulty=difficulty_param)

        channel_param = self.request.query_params.get("channel")
        if channel_param:
            qs = qs.filter(channel=channel_param)

        is_scam_param = self.request.query_params.get("is_scam")
        if is_scam_param is not None:
            if is_scam_param.lower() in ("true", "1"):
                qs = qs.filter(is_scam=True)
            elif is_scam_param.lower() in ("false", "0"):
                qs = qs.filter(is_scam=False)

        return qs.select_related("author").prefetch_related("red_flags").order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StudioScenarioCreateSerializer
        return StudioScenarioSerializer

    @extend_schema(
        summary="Create simulator scenario draft",
        request=StudioScenarioCreateSerializer,
        responses={201: StudioScenarioSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = StudioScenarioCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image_file = request.FILES.get("image")
        scenario = simulator_service.create_scenario(
            data=serializer.validated_data,
            author=request.user,
            image_file=image_file,
        )
        out_serializer = StudioScenarioSerializer(scenario, context={"request": request})
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class StudioScenarioDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Studio scenario detail, update & delete endpoint.
    EDUCATOR can only view/update/delete scenarios they authored.
    ADMIN has unrestricted access across all scenarios.
    """

    permission_classes = [IsScenarioAuthorOrAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = StudioScenarioSerializer

    def get_queryset(self):
        return SimulatorScenario.objects.all().select_related("author").prefetch_related("red_flags")

    @extend_schema(
        summary="Update simulator scenario",
        request=StudioScenarioUpdateSerializer,
        responses={200: StudioScenarioSerializer},
    )
    def patch(self, request, *args, **kwargs):
        scenario = self.get_object()
        serializer = StudioScenarioUpdateSerializer(instance=scenario, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        image_file = request.FILES.get("image")
        scenario = simulator_service.update_scenario(
            scenario=scenario,
            data=serializer.validated_data,
            image_file=image_file,
        )
        out_serializer = StudioScenarioSerializer(scenario, context={"request": request})
        return Response(out_serializer.data)

    def delete(self, request, *args, **kwargs):
        scenario = self.get_object()
        simulator_service.delete_scenario(scenario)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudioScenarioPublishView(APIView):
    """Publishes a scenario enforcing red-flag rules."""

    permission_classes = [IsScenarioAuthorOrAdmin]
    serializer_class = StudioScenarioSerializer

    @extend_schema(
        summary="Publish simulator scenario",
        responses={200: StudioScenarioSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        scenario = get_object_or_404(
            SimulatorScenario.objects.select_related("author").prefetch_related("red_flags"),
            pk=pk,
        )
        self.check_object_permissions(request, scenario)
        scenario = simulator_service.publish_scenario(scenario)
        serializer = StudioScenarioSerializer(scenario, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudioScenarioUnpublishView(APIView):
    """Transitions a published scenario back to DRAFT."""

    permission_classes = [IsScenarioAuthorOrAdmin]
    serializer_class = StudioScenarioSerializer

    @extend_schema(
        summary="Unpublish simulator scenario",
        responses={200: StudioScenarioSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        scenario = get_object_or_404(
            SimulatorScenario.objects.select_related("author").prefetch_related("red_flags"),
            pk=pk,
        )
        self.check_object_permissions(request, scenario)
        scenario = simulator_service.unpublish_scenario(scenario)
        serializer = StudioScenarioSerializer(scenario, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudioScenarioArchiveView(APIView):
    """Transitions a scenario to ARCHIVED."""

    permission_classes = [IsScenarioAuthorOrAdmin]
    serializer_class = StudioScenarioSerializer

    @extend_schema(
        summary="Archive simulator scenario",
        responses={200: StudioScenarioSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        scenario = get_object_or_404(
            SimulatorScenario.objects.select_related("author").prefetch_related("red_flags"),
            pk=pk,
        )
        self.check_object_permissions(request, scenario)
        scenario = simulator_service.archive_scenario(scenario)
        serializer = StudioScenarioSerializer(scenario, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudioScenarioRedFlagListCreateView(APIView):
    """List and create red flag hotspots for a scenario."""

    permission_classes = [IsScenarioAuthorOrAdmin]

    def get_scenario(self, request, scenario_id):
        scenario = get_object_or_404(SimulatorScenario, pk=scenario_id)
        self.check_object_permissions(request, scenario)
        return scenario

    @extend_schema(
        summary="List red flags for scenario",
        responses={200: ScenarioRedFlagSerializer(many=True)},
    )
    def get(self, request, pk, *args, **kwargs):
        scenario = self.get_scenario(request, pk)
        flags = scenario.red_flags.all().order_by("id")
        serializer = ScenarioRedFlagSerializer(flags, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Add red flag hotspot to scenario",
        request=ScenarioRedFlagCreateSerializer,
        responses={201: ScenarioRedFlagSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        scenario = self.get_scenario(request, pk)
        serializer = ScenarioRedFlagCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flag = simulator_service.add_red_flag(scenario, serializer.validated_data)
        out_serializer = ScenarioRedFlagSerializer(flag)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class StudioScenarioRedFlagDetailView(APIView):
    """Delete a red flag hotspot from a scenario."""

    permission_classes = [IsScenarioAuthorOrAdmin]

    @extend_schema(
        summary="Delete red flag hotspot from scenario",
        responses={204: None},
    )
    def delete(self, request, pk, flag_id, *args, **kwargs):
        scenario = get_object_or_404(SimulatorScenario, pk=pk)
        self.check_object_permissions(request, scenario)
        flag = get_object_or_404(ScenarioRedFlag, pk=flag_id, scenario=scenario)
        simulator_service.delete_red_flag(flag)
        return Response(status=status.HTTP_204_NO_CONTENT)
