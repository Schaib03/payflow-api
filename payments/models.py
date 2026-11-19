import uuid

from django.db import models
from django.db.models import F, Q


class Currency(models.TextChoices):
    MAD = "MAD"
    EUR = "EUR"
    USD = "USD"


class Payment(models.Model):
    class Status(models.TextChoices):
        SUCCEEDED = "succeeded"
        FAILED = "failed"
        PARTIALLY_REFUNDED = "partially_refunded"
        REFUNDED = "refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.PROTECT, related_name="payments"
    )
    # Amounts are integers in minor units (centimes, cents) to avoid float rounding.
    amount = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, choices=Currency.choices)
    status = models.CharField(max_length=20, choices=Status.choices)
    amount_refunded = models.PositiveBigIntegerField(default=0)
    fee = models.PositiveBigIntegerField(default=0)
    description = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    # Only non-sensitive card data. The full number never reaches the database.
    card_brand = models.CharField(max_length=20)
    card_last4 = models.CharField(max_length=4)
    card_exp_month = models.PositiveSmallIntegerField()
    card_exp_year = models.PositiveSmallIntegerField()
    failure_code = models.CharField(max_length=40, blank=True, default="")
    failure_message = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["merchant", "-created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_refunded__lte=F("amount")),
                name="payment_refund_not_above_amount",
            )
        ]

    def __str__(self):
        return f"{self.id} {self.amount} {self.currency} {self.status}"

    @property
    def refundable_amount(self):
        if self.status not in (self.Status.SUCCEEDED, self.Status.PARTIALLY_REFUNDED):
            return 0
        return self.amount - self.amount_refunded


class Refund(models.Model):
    class Reason(models.TextChoices):
        REQUESTED_BY_CUSTOMER = "requested_by_customer"
        DUPLICATE = "duplicate"
        FRAUDULENT = "fraudulent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, choices=Currency.choices)
    reason = models.CharField(max_length=30, choices=Reason.choices, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"refund {self.id} of {self.amount} {self.currency}"
