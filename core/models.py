from django.db import models


class IdempotencyKey(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"

    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="idempotency_keys"
    )
    key = models.CharField(max_length=255)
    # SHA-256 of method + path + canonical JSON body. The body itself is not stored
    # because it can contain a card number.
    request_fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "key"], name="idempotency_unique_key")
        ]
        indexes = [models.Index(fields=["created_at"])]

    def __str__(self):
        return f"{self.merchant_id}:{self.key}"
