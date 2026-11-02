from django.urls import path

from apps.alerts.views import (
    SubscriptionConfirmView,
    SubscriptionCreateView,
    SubscriptionUnsubscribeView,
)

urlpatterns = [
    path("subscriptions/", SubscriptionCreateView.as_view(), name="alert-subscription-create"),
    path(
        "subscriptions/confirm/",
        SubscriptionConfirmView.as_view(),
        name="alert-subscription-confirm",
    ),
    path(
        "subscriptions/unsubscribe/",
        SubscriptionUnsubscribeView.as_view(),
        name="alert-subscription-unsubscribe",
    ),
]
