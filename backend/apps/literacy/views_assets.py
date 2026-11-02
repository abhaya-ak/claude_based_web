from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.literacy.models import EducationalGuide, GuideAsset
from apps.literacy.permissions import IsGuideAuthorOrAdmin
from apps.literacy.serializers import GuideAssetSerializer
from apps.literacy.services import asset_service


class StudioGuideAssetListCreateView(APIView):
    """Studio endpoint to upload media assets for an educational guide."""

    permission_classes = [IsGuideAuthorOrAdmin]
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = GuideAssetSerializer

    @extend_schema(
        summary="Upload media asset for guide",
        responses={201: GuideAssetSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        guide = get_object_or_404(EducationalGuide, pk=pk)
        self.check_object_permissions(request, guide)

        file_obj = request.FILES.get("file")
        if not file_obj:
            raise ValidationError({"file": ["No file was submitted."]}, code="validation_error")

        asset = asset_service.upload_guide_asset(guide, file_obj, request.data)
        serializer = GuideAssetSerializer(asset, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StudioGuideAssetDetailView(APIView):
    """Studio endpoint to delete a media asset from a guide and S3."""

    permission_classes = [IsGuideAuthorOrAdmin]
    serializer_class = GuideAssetSerializer

    @extend_schema(
        summary="Delete media asset from guide",
        responses={204: None},
    )
    def delete(self, request, pk, asset_id, *args, **kwargs):
        guide = get_object_or_404(EducationalGuide, pk=pk)
        self.check_object_permissions(request, guide)

        asset = get_object_or_404(GuideAsset, pk=asset_id, guide=guide)
        asset_service.delete_guide_asset(asset)
        return Response(status=status.HTTP_204_NO_CONTENT)
