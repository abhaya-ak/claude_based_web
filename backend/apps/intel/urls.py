from django.urls import path

from apps.intel.views import TriageQueueView, TriageReportDetailView

urlpatterns = [
    path("queue/", TriageQueueView.as_view(), name="triage-queue"),
    path("reports/<uuid:id>/", TriageReportDetailView.as_view(), name="triage-report-detail"),
]
