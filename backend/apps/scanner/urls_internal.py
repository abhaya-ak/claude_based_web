from django.urls import path

from apps.scanner.views_internal import ScanResultCallbackView

urlpatterns = [
    path("scan-results/", ScanResultCallbackView.as_view(), name="internal-scan-results"),
]
