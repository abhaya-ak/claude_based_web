from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

urlpatterns = [
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/admin-portal/users/", include("apps.accounts.urls_admin")),
]
