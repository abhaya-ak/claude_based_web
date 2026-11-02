from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reports.serializers import LookupRequestSerializer, LookupResponseSerializer
from apps.reports.services.lookup_service import determine_verdict
from apps.reports.throttling import LookupRateThrottle


class LookupView(APIView):
    """
    Public threat lookup endpoint (D102, D103).
    Evaluates candidate indicators against active verified indicators and pending reports.
    Rate limited to 30 requests/minute per IP hash.
    Never leaks PII (R-C5, R-C8).
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [LookupRateThrottle]
    throttle_scope = "lookups"

    @extend_schema(
        request=LookupRequestSerializer,
        responses={200: LookupResponseSerializer},
        description="Lookup phone numbers, URLs, domains, emails, or bank accounts against known threat intel.",
    )
    def post(self, request, *args, **kwargs):
        serializer = LookupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data["query"]
        result = determine_verdict(query)
        response_serializer = LookupResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
