from django.urls import path

from apps.accounts.views.auth_views import (
    CitizenRegisterView,
    LoginView,
    LogoutView,
    RefreshView,
    StaffRegisterView,
)
from apps.accounts.views.user_views import CurrentUserView, PasswordChangeView

app_name = "accounts"

urlpatterns = [
    path("register/", CitizenRegisterView.as_view(), name="register"),
    path("register/staff/", StaffRegisterView.as_view(), name="register_staff"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
]
