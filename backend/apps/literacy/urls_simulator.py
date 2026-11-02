from django.urls import path

from apps.literacy.views_simulator import (
    SimulatorAttemptAnswerView,
    SimulatorAttemptCompleteView,
    SimulatorAttemptDetailView,
    SimulatorAttemptInitView,
)

urlpatterns = [
    path("attempts/", SimulatorAttemptInitView.as_view(), name="simulator-attempt-init"),
    path("attempts/<uuid:pk>/", SimulatorAttemptDetailView.as_view(), name="simulator-attempt-detail"),
    path("attempts/<uuid:pk>/answers/", SimulatorAttemptAnswerView.as_view(), name="simulator-attempt-answer"),
    path("attempts/<uuid:pk>/complete/", SimulatorAttemptCompleteView.as_view(), name="simulator-attempt-complete"),
]
