from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.scanner.permissions import HasValidScannerSignature
from apps.scanner.serializers import ScanResultCallbackSerializer
from apps.scanner.services.callback_service import process_scan_result
from apps.scanner.throttling import ScannerCallbackThrottle


class ScanResultCallbackView(APIView):
    """
    Internal machine-to-machine callback endpoint for heuristic scanner results (D90, D91).
    Secured by HMAC-SHA256 signature and timestamp verification.
    """

    authentication_classes = []
    permission_classes = [HasValidScannerSignature]
    throttle_classes = [ScannerCallbackThrottle]
    serializer_class = ScanResultCallbackSerializer

    @extend_schema(
        summary="Internal scanner callback",
        description="Receives scoring results from heuristic scanner Lambda, verified via HMAC-SHA256.",
        request=ScanResultCallbackSerializer,
        responses={
            200: OpenApiResponse(description="Scan result processed and saved successfully."),
            400: OpenApiResponse(description="Validation error in result payload."),
            403: OpenApiResponse(description="Invalid signature, bad timestamp, or clock skew."),
            404: OpenApiResponse(description="Report not found."),
            429: OpenApiResponse(description="Throttled."),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        _, report = process_scan_result(
            report_id=data["report_id"],
            ruleset_version=data["ruleset_version"],
            risk_score=data["risk_score"],
            is_high_priority=data["is_high_priority"],
            breakdown=data["breakdown"],
            lambda_request_id=data.get("lambda_request_id"),
        )

        return Response(
            {
                "status": "ok",
                "reference_code": report.reference_code,
            },
            status=status.HTTP_200_OK,
        )
