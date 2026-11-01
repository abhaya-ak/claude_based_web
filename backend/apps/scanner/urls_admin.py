from django.urls import path

from apps.scanner.views_admin import RuleDetailView, RuleListCreateView, ScannerConfigView

app_name = "scanner_admin"

urlpatterns = [
    path("rules/", RuleListCreateView.as_view(), name="rule_list_create"),
    path("rules/<int:pk>/", RuleDetailView.as_view(), name="rule_detail"),
    path("scanner-config/", ScannerConfigView.as_view(), name="scanner_config"),
]
