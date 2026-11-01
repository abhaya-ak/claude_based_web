from django.urls import path

from apps.reports.views import (
    MyReportsView,
    ReportCreateView,
    ReportOptionsView,
    ReportTrackView,
)

urlpatterns = [
    path("options/", ReportOptionsView.as_view(), name="report-options"),
    path("", ReportCreateView.as_view(), name="report-create"),
    path("track/", ReportTrackView.as_view(), name="report-track"),
    path("mine/", MyReportsView.as_view(), name="report-mine"),
]
