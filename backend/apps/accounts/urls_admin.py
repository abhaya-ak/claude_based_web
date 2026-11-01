from django.urls import path

from apps.accounts.views.admin_views import (
    AdminUserApproveView,
    AdminUserChangeRoleView,
    AdminUserListView,
    AdminUserRejectView,
)

app_name = "admin_accounts"

urlpatterns = [
    path("", AdminUserListView.as_view(), name="user_list"),
    path("<uuid:pk>/approve/", AdminUserApproveView.as_view(), name="user_approve"),
    path("<uuid:pk>/reject/", AdminUserRejectView.as_view(), name="user_reject"),
    path("<uuid:pk>/change-role/", AdminUserChangeRoleView.as_view(), name="user_change_role"),
]
