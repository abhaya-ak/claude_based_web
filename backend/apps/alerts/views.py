from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alerts.serializers import (
    SubscriptionActionResponseSerializer,
    SubscriptionCreateRequestSerializer,
    SubscriptionResponseSerializer,
    SubscriptionTokenRequestSerializer,
)
from apps.alerts.services.subscription_service import (
    confirm_subscription,
    create_subscription,
    unsubscribe_subscription,
)


class SubscriptionCreateView(APIView):
    """
    Public alert subscription creation endpoint (D104).
    Validates channel, endpoint, and audience, subscribes to SNS with FilterPolicy.
    Duplicate requests return existing record without leaking state.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=SubscriptionCreateRequestSerializer,
        responses={
            201: SubscriptionResponseSerializer,
            200: SubscriptionResponseSerializer,
        },
        description="Subscribe to threat alert broadcasts via email or SMS.",
    )
    def post(self, request, *args, **kwargs):
        serializer = SubscriptionCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sub, raw_token, is_created = create_subscription(
            serializer.validated_data, user=request.user
        )
        msg = (
            "Subscription created. Please check your endpoint to confirm."
            if is_created
            else "Subscription request received. Please check your endpoint to confirm."
        )
        resp_data = {
            "id": sub.id,
            "channel": sub.channel,
            "audience": sub.audience,
            "categories": sub.categories,
            "status": sub.status,
            "message": msg,
            "token": raw_token if is_created else None,
        }
        status_code = status.HTTP_201_CREATED if is_created else status.HTTP_200_OK
        return Response(SubscriptionResponseSerializer(resp_data).data, status=status_code)


class SubscriptionConfirmView(APIView):
    """
    Public alert subscription confirmation endpoint (D105).
    Confirms subscription using token.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=SubscriptionTokenRequestSerializer,
        responses={200: SubscriptionActionResponseSerializer},
        description="Confirm an alert subscription with secure token.",
    )
    def post(self, request, *args, **kwargs):
        serializer = SubscriptionTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sub = confirm_subscription(serializer.validated_data["token"])
        return Response(
            SubscriptionActionResponseSerializer(
                {"status": sub.status, "message": "Subscription confirmed successfully."}
            ).data,
            status=status.HTTP_200_OK,
        )


class SubscriptionUnsubscribeView(APIView):
    """
    Public alert unsubscription endpoint (D105).
    Unsubscribes from alert topic using token.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=SubscriptionTokenRequestSerializer,
        responses={200: SubscriptionActionResponseSerializer},
        description="Unsubscribe from threat alerts with secure token.",
    )
    def post(self, request, *args, **kwargs):
        serializer = SubscriptionTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sub = unsubscribe_subscription(serializer.validated_data["token"])
        return Response(
            SubscriptionActionResponseSerializer(
                {
                    "status": sub.status,
                    "message": "You have been unsubscribed successfully.",
                }
            ).data,
            status=status.HTTP_200_OK,
        )
