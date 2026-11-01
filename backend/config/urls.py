from django.urls import include, path

urlpatterns = [
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/admin-portal/users/", include("apps.accounts.urls_admin")),
]
