from rest_framework import serializers

from webhooks.models import EVENT_TYPES, Event, WebhookDelivery, WebhookEndpoint


class WebhookEndpointSerializer(serializers.ModelSerializer):
    enabled_events = serializers.ListField(
        child=serializers.ChoiceField(choices=["*", *EVENT_TYPES]),
        allow_empty=False,
        default=["*"],
    )

    class Meta:
        model = WebhookEndpoint
        fields = ["id", "url", "description", "enabled_events", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_url(self, value):
        if not value.startswith(("https://", "http://")):
            raise serializers.ValidationError("Only http(s) URLs are supported.")
        return value


class WebhookEndpointCreatedSerializer(WebhookEndpointSerializer):
    class Meta(WebhookEndpointSerializer.Meta):
        fields = [*WebhookEndpointSerializer.Meta.fields, "secret"]
        read_only_fields = [*WebhookEndpointSerializer.Meta.read_only_fields, "secret"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "type", "data", "created_at"]
        read_only_fields = fields


class WebhookDeliverySerializer(serializers.ModelSerializer):
    event_type = serializers.CharField(source="event.type", read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "event",
            "event_type",
            "status",
            "attempts",
            "last_status_code",
            "last_error",
            "next_attempt_at",
            "delivered_at",
            "created_at",
        ]
        read_only_fields = fields
