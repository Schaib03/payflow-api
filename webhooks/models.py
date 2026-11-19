import secrets
import uuid

from django.db import models

EVENT_TYPES = ["payment.succeeded", "payment.failed", "refund.created"]


def generate_secret():
    return "whsec_" + secrets.token_urlsafe(32)


class WebhookEndpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="webhook_endpoints"
    )
    url = models.URLField(max_length=500)
    description = models.CharField(max_length=255, blank=True, default="")
    # Event types this endpoint wants; "*" means all of them.
    enabled_events = models.JSONField(default=list)
    secret = models.CharField(max_length=64, default=generate_secret)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.url

    def accepts(self, event_type):
        return "*" in self.enabled_events or event_type in self.enabled_events


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="events"
    )
    type = models.CharField(max_length=64, db_index=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["merchant", "-created_at"])]

    def __str__(self):
        return f"{self.type} {self.id}"


class WebhookDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="deliveries")
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True, default="")
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["event", "endpoint"], name="delivery_unique_target")
        ]

    def __str__(self):
        return f"{self.event_id} -> {self.endpoint_id} ({self.status})"
