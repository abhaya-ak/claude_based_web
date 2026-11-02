from django.urls import path

from apps.literacy.views_studio import (
    StudioGuideArchiveView,
    StudioGuideDetailView,
    StudioGuideListCreateView,
    StudioGuidePublishView,
    StudioGuideUnpublishView,
)

urlpatterns = [
    path("", StudioGuideListCreateView.as_view(), name="studio-guide-list-create"),
    path("<uuid:pk>/", StudioGuideDetailView.as_view(), name="studio-guide-detail"),
    path("<uuid:pk>/publish/", StudioGuidePublishView.as_view(), name="studio-guide-publish"),
    path("<uuid:pk>/unpublish/", StudioGuideUnpublishView.as_view(), name="studio-guide-unpublish"),
    path("<uuid:pk>/archive/", StudioGuideArchiveView.as_view(), name="studio-guide-archive"),
]
