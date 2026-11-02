from django.urls import path

from apps.reports.views_lookup import LookupView

urlpatterns = [
    path("", LookupView.as_view(), name="threat-lookup"),
]
