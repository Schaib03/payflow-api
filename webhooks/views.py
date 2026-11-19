from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from webhooks.models import EVENT_TYPES, Event, WebhookDelivery, WebhookEndpoint
from webhooks.serializers import (
    EventSerializer,
    WebhookDeliverySerializer,
    WebhookEndpointCreatedSerializer,
    WebhookEndpointSerializer,
)


class WebhookEndpointListCreateView(generics.ListAPIView):
    serializer_class = WebhookEndpointSerializer

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(merchant=self.request.user)

    @extend_schema(
        request=WebhookEndpointSerializer,
        responses={201: WebhookEndpointCreatedSerializer},
        summary="Register a webhook endpoint (the response contains its signing secret)",
    )
    def post(self, request):
        serializer = WebhookEndpointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        endpoint = serializer.save(merchant=request.user)
        return Response(
            WebhookEndpointCreatedSerializer(endpoint).data, status=status.HTTP_201_CREATED
        )


class WebhookEndpointDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WebhookEndpointSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(merchant=self.request.user)


class WebhookDeliveryListView(generics.ListAPIView):
    serializer_class = WebhookDeliverySerializer

    def get_queryset(self):
        endpoint = get_object_or_404(
            WebhookEndpoint, pk=self.kwargs["pk"], merchant=self.request.user
        )
        return WebhookDelivery.objects.filter(endpoint=endpoint).select_related("event")


class EventListView(generics.ListAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        queryset = Event.objects.filter(merchant=self.request.user)
        event_type = self.request.query_params.get("type")
        if event_type:
            queryset = queryset.filter(type=event_type)
        return queryset

    @extend_schema(
        parameters=[OpenApiParameter("type", str, enum=EVENT_TYPES)],
        summary="List events, newest first",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class EventDetailView(generics.RetrieveAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.filter(merchant=self.request.user)
