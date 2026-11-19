from django.urls import path

from webhooks import views

urlpatterns = [
    path("webhook-endpoints", views.WebhookEndpointListCreateView.as_view(), name="webhook-list"),
    path(
        "webhook-endpoints/<uuid:pk>",
        views.WebhookEndpointDetailView.as_view(),
        name="webhook-detail",
    ),
    path(
        "webhook-endpoints/<uuid:pk>/deliveries",
        views.WebhookDeliveryListView.as_view(),
        name="webhook-deliveries",
    ),
    path("events", views.EventListView.as_view(), name="event-list"),
    path("events/<uuid:pk>", views.EventDetailView.as_view(), name="event-detail"),
]
