from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


@api_view(["GET"])
@permission_classes([AllowAny])
def health_liveness(request):
    return JsonResponse({"status": "ok"}, status=200)


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
