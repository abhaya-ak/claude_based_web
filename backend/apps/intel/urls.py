from django.urls import path

from apps.intel.views import (
    TriageEvidenceView,
    TriageQueueView,
    TriageRejectReportView,
    TriageReportDetailView,
)

urlpatterns = [
    path("queue/", TriageQueueView.as_view(), name="triage-queue"),
    path("reports/<uuid:id>/", TriageReportDetailView.as_view(), name="triage-report-detail"),
    path("reports/<uuid:id>/evidence/", TriageEvidenceView.as_view(), name="triage-evidence"),
    path("reports/<uuid:id>/reject/", TriageRejectReportView.as_view(), name="triage-reject-report"),
]
