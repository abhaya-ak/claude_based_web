from django.urls import path

from apps.broadcasts.views_advisories import (
    AdvisoryDetailView,
    AdvisoryListCreateView,
    AdvisoryPublishView,
)

urlpatterns = [
    path("", AdvisoryListCreateView.as_view(), name="advisory-list-create"),
    path("<uuid:pk>/", AdvisoryDetailView.as_view(), name="advisory-detail"),
    path("<uuid:pk>/publish/", AdvisoryPublishView.as_view(), name="advisory-publish"),
]
