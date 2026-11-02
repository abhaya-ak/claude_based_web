from django.urls import path

from apps.literacy.views_scenarios import (
    StudioScenarioArchiveView,
    StudioScenarioDetailView,
    StudioScenarioListCreateView,
    StudioScenarioPublishView,
    StudioScenarioRedFlagDetailView,
    StudioScenarioRedFlagListCreateView,
    StudioScenarioUnpublishView,
)

urlpatterns = [
    path("", StudioScenarioListCreateView.as_view(), name="studio-scenario-list-create"),
    path("<uuid:pk>/", StudioScenarioDetailView.as_view(), name="studio-scenario-detail"),
    path("<uuid:pk>/publish/", StudioScenarioPublishView.as_view(), name="studio-scenario-publish"),
    path("<uuid:pk>/unpublish/", StudioScenarioUnpublishView.as_view(), name="studio-scenario-unpublish"),
    path("<uuid:pk>/archive/", StudioScenarioArchiveView.as_view(), name="studio-scenario-archive"),
    path("<uuid:pk>/flags/", StudioScenarioRedFlagListCreateView.as_view(), name="studio-scenario-flags-list-create"),
    path("<uuid:pk>/flags/<int:flag_id>/", StudioScenarioRedFlagDetailView.as_view(), name="studio-scenario-flag-detail"),
]
