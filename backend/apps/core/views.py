from django.db import connection
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


@extend_schema(
    summary="Health check liveness",
    description="Returns 200 OK if the service is running.",
    responses={
        200: inline_serializer(
            name="LivenessResponse",
            fields={"status": serializers.CharField()},
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_liveness(request):
    return JsonResponse({"status": "ok"}, status=200)


@extend_schema(
    summary="Health check readiness",
    description="Returns 200 OK if the database is reachable and responsive.",
    responses={
        200: inline_serializer(
            name="ReadinessResponse",
            fields={
                "status": serializers.CharField(),
                "database": serializers.CharField(),
            },
        ),
        503: inline_serializer(
            name="UnavailableResponse",
            fields={
                "status": serializers.CharField(),
                "database": serializers.CharField(),
            },
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ready", "database": "ok"}, status=200)
    except Exception:
        return JsonResponse({"status": "unavailable", "database": "error"}, status=503)
