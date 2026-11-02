from django.urls import path

from apps.literacy.views_public import PublicGuideDetailView, PublicGuideListView

urlpatterns = [
    path("", PublicGuideListView.as_view(), name="public-guide-list"),
    path("<slug:slug>/", PublicGuideDetailView.as_view(), name="public-guide-detail"),
]
