from django.urls import path

from apps.broadcasts.views_analytics import (
    LossesAnalyticsView,
    SpikesAnalyticsView,
    TacticsAnalyticsView,
    VolumeAnalyticsView,
)

urlpatterns = [
    path("volume/", VolumeAnalyticsView.as_view(), name="analytics-volume"),
    path("losses/", LossesAnalyticsView.as_view(), name="analytics-losses"),
    path("tactics/", TacticsAnalyticsView.as_view(), name="analytics-tactics"),
    path("spikes/", SpikesAnalyticsView.as_view(), name="analytics-spikes"),
]
