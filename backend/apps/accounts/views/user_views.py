from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.cookies import clear_refresh_cookie
from apps.accounts.serializers.user import PasswordChangeSerializer, UserProfileSerializer
from apps.accounts.services.user_service import change_user_password
from apps.core.ip import client_ip_hash


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get current user profile",
        responses={200: UserProfileSerializer},
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change user password and revoke sessions",
        request=PasswordChangeSerializer,
        responses={204: None},
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        ip_hash = client_ip_hash(request)

        change_user_password(
            user=request.user,
            new_password=serializer.validated_data["new_password"],
            ip_hash=ip_hash,
        )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response
