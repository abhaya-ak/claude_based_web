from django.core.cache import cache
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole
from apps.broadcasts.selectors.analytics_selectors import (
    get_losses_analytics,
    get_spikes_analytics,
    get_tactics_analytics,
    get_volume_analytics,
    validate_date_range,
)
from apps.broadcasts.serializers import (
    LossesAnalyticsResponseSerializer,
    SpikeDetailSerializer,
    TacticCountSerializer,
    VolumeAnalyticsResponseSerializer,
)

CACHE_TTL = 60  # seconds


class VolumeAnalyticsView(APIView):
    """Returns report volume metrics aggregated by day, platform, and category per D106."""

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST, Role.ADMIN)]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="start_date", description="Start date (YYYY-MM-DD)", required=False, type=str),
            OpenApiParameter(name="end_date", description="End date (YYYY-MM-DD)", required=False, type=str),
        ],
        responses={200: VolumeAnalyticsResponseSerializer},
        description="Aggregate scam report volume breakdown by day, platform, and category.",
    )
    def get(self, request, *args, **kwargs):
        start_date, end_date = validate_date_range(
            request.query_params.get("start_date"),
            request.query_params.get("end_date"),
        )
        cache_key = f"analytics:volume:{start_date}:{end_date}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            response = Response(cached_data)
            response["Cache-Control"] = f"private, max-age={CACHE_TTL}"
            return response

        data = get_volume_analytics(start_date, end_date)
        cache.set(cache_key, data, timeout=CACHE_TTL)
        response = Response(data)
        response["Cache-Control"] = f"private, max-age={CACHE_TTL}"
        return response


class LossesAnalyticsView(APIView):
    """Returns financial loss metrics grouped by country, admin area, and currency per D106."""

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST, Role.ADMIN)]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="start_date", description="Start date (YYYY-MM-DD)", required=False, type=str),
            OpenApiParameter(name="end_date", description="End date (YYYY-MM-DD)", required=False, type=str),
        ],
        responses={200: LossesAnalyticsResponseSerializer},
        description="Aggregate financial losses and report counts by country and admin area.",
    )
    def get(self, request, *args, **kwargs):
        start_date, end_date = validate_date_range(
            request.query_params.get("start_date"),
            request.query_params.get("end_date"),
        )
        cache_key = f"analytics:losses:{start_date}:{end_date}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            response = Response(cached_data)
            response["Cache-Control"] = f"private, max-age={CACHE_TTL}"
            return response

        data = get_losses_analytics(start_date, end_date)
        cache.set(cache_key, data, timeout=CACHE_TTL)
        response = Response(data)
        response["Cache-Control"] = f"private, max-age={CACHE_TTL}"
        return response


class TacticsAnalyticsView(APIView):
    """Returns manipulation tactic frequencies extracted from scan results and categories per D107."""

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST, Role.ADMIN)]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="start_date", description="Start date (YYYY-MM-DD)", required=False, type=str),
            OpenApiParameter(name="end_date", description="End date (YYYY-MM-DD)", required=False, type=str),
        ],
        responses={200: TacticCountSerializer(many=True)},
        description="Aggregate social engineering tactic frequencies (URGENCY, AUTHORITY, FEAR, GREED).",
    )
    def get(self, request, *args, **kwargs):
        start_date, end_date = validate_date_range(
            request.query_params.get("start_date"),
            request.query_params.get("end_date"),
        )
        cache_key = f"analytics:tactics:{start_date}:{end_date}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            response = Response(cached_data)
            response["Cache-Control"] = f"private, max-age={CACHE_TTL}"
            return response

        data = get_tactics_analytics(start_date, end_date)
        cache.set(cache_key, data, timeout=CACHE_TTL)
        response = Response(data)
        response["Cache-Control"] = f"private, max-age={CACHE_TTL}"
        return response


class SpikesAnalyticsView(APIView):
    """Returns detected volume spikes comparing last 24h against trailing 7-day daily average per D107."""

    permission_classes = [IsAuthenticated, HasRole(Role.ANALYST, Role.ADMIN)]

    @extend_schema(
        responses={200: SpikeDetailSerializer(many=True)},
        description="Trend spikes exceeding +300% growth with minimum 5 report threshold in last 24h.",
    )
    def get(self, request, *args, **kwargs):
        cache_key = "analytics:spikes"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            response = Response(cached_data)
            response["Cache-Control"] = f"private, max-age={CACHE_TTL}"
            return response

        data = get_spikes_analytics()
        cache.set(cache_key, data, timeout=CACHE_TTL)
        response = Response(data)
        response["Cache-Control"] = f"private, max-age={CACHE_TTL}"
        return response
