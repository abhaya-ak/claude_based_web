from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.cookies import clear_refresh_cookie, require_csrf_header, set_refresh_cookie
from apps.accounts.serializers.auth import (
    CitizenRegisterSerializer,
    LoginSerializer,
    StaffRegisterSerializer,
    UserSummarySerializer,
)
from apps.accounts.services.auth_service import (
    login_user,
    logout_user,
    refresh_token,
    register_citizen,
    register_staff,
)
from apps.core.ip import client_ip_hash


class CitizenRegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "anon_auth"

    @extend_schema(
        summary="Citizen registration",
        request=CitizenRegisterSerializer,
        responses={201: UserSummarySerializer},
        auth=[],
    )
    def post(self, request):
        serializer = CitizenRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip_hash = client_ip_hash(request)

        user = register_citizen(serializer.validated_data, ip_hash=ip_hash)
        return Response(
            {"user": UserSummarySerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class StaffRegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "anon_auth"

    @extend_schema(
        summary="Staff registration (pending approval)",
        request=StaffRegisterSerializer,
        responses={201: OpenApiResponse(description="Staff registration submitted")},
        auth=[],
    )
    def post(self, request):
        serializer = StaffRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip_hash = client_ip_hash(request)

        user = register_staff(serializer.validated_data, ip_hash=ip_hash)
        return Response(
            {
                "message": "Registration submitted. Staff accounts require administrator approval before login.",
                "user": UserSummarySerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "anon_auth"

    @extend_schema(
        summary="User login",
        request=LoginSerializer,
        responses={200: OpenApiResponse(description="Access token returned and refresh cookie set")},
        auth=[],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip_hash = client_ip_hash(request)

        user, access_token, refresh_tok = login_user(
            email=serializer.validated_data["email"],
            raw_password=serializer.validated_data["password"],
            ip_hash=ip_hash,
        )

        response = Response(
            {
                "access": access_token,
                "user": UserSummarySerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
        set_refresh_cookie(response, refresh_tok)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "anon_auth"

    @extend_schema(
        summary="Refresh access token",
        request=None,
        responses={200: OpenApiResponse(description="New access token returned and rotated cookie set")},
        auth=[],
    )
    def post(self, request):
        require_csrf_header(request)
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh")
        raw_refresh = request.COOKIES.get(cookie_name)

        new_access, new_refresh = refresh_token(raw_refresh)
        response = Response({"access": new_access}, status=status.HTTP_200_OK)
        set_refresh_cookie(response, new_refresh)
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "anon_auth"

    @extend_schema(
        summary="User logout",
        request=None,
        responses={204: None},
        auth=[],
    )
    def post(self, request):
        require_csrf_header(request)
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh")
        raw_refresh = request.COOKIES.get(cookie_name)

        logout_user(raw_refresh)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response
