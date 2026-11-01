from rest_framework import exceptions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import ApprovalStatus, Role, User
from apps.accounts.permissions import HasRole
from apps.accounts.serializers.admin import (
    AdminUserSerializer,
    ChangeRoleSerializer,
    RejectUserSerializer,
)
from apps.accounts.services.admin_service import (
    approve_staff_user,
    change_user_role,
    reject_staff_user,
)
from apps.core.ip import client_ip_hash


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]

    def get(self, request):
        status_param = request.query_params.get("status")
        qs = User.objects.select_related("approved_by").order_by("-created_at", "id")

        if status_param is not None:
            status_val = status_param.upper()
            if status_val not in ApprovalStatus.values:
                raise exceptions.ValidationError({"status": ["Invalid status value."]})
            qs = qs.filter(approval_status=status_val)

        serializer = AdminUserSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminUserApproveView(APIView):
    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]

    def post(self, request, pk):
        ip_hash = client_ip_hash(request)
        user = approve_staff_user(admin_user=request.user, target_id=pk, ip_hash=ip_hash)
        return Response(AdminUserSerializer(user).data, status=status.HTTP_200_OK)


class AdminUserRejectView(APIView):
    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]

    def post(self, request, pk):
        serializer = RejectUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip_hash = client_ip_hash(request)

        user = reject_staff_user(
            admin_user=request.user,
            target_id=pk,
            reason=serializer.validated_data["reason"],
            ip_hash=ip_hash,
        )
        return Response(AdminUserSerializer(user).data, status=status.HTTP_200_OK)


class AdminUserChangeRoleView(APIView):
    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]

    def post(self, request, pk):
        serializer = ChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip_hash = client_ip_hash(request)

        user = change_user_role(
            admin_user=request.user,
            target_id=pk,
            new_role=serializer.validated_data["role"],
            ip_hash=ip_hash,
        )
        return Response(AdminUserSerializer(user).data, status=status.HTTP_200_OK)
