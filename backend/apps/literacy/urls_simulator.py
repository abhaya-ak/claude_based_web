from django.urls import path

from apps.literacy.views_simulator import SimulatorAttemptInitView

urlpatterns = [
    path("attempts/", SimulatorAttemptInitView.as_view(), name="simulator-attempt-init"),
]
