import uuid

from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce


class Direction(models.TextChoices):
    DEBIT = "debit"
    CREDIT = "credit"


class LedgerAccount(models.Model):
    class Code(models.TextChoices):
        # Asset: money the card processor owes us / holds for us.
        PROCESSOR_CLEARING = "processor_clearing"
        # Liability: money we owe the merchant.
        MERCHANT_BALANCE = "merchant_balance"
        # Revenue: our fees.
        PLATFORM_FEES = "platform_fees"

    NORMAL_SIDES = {
        Code.PROCESSOR_CLEARING: Direction.DEBIT,
        Code.MERCHANT_BALANCE: Direction.CREDIT,
        Code.PLATFORM_FEES: Direction.CREDIT,
    }

    code = models.CharField(max_length=32, choices=Code.choices)
    currency = models.CharField(max_length=3)
    merchant = models.ForeignKey(
        "merchants.Merchant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ledger_accounts",
    )
    normal_side = models.CharField(max_length=6, choices=Direction.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code", "currency", "merchant"], name="ledger_unique_merchant_account"
            ),
            # NULLs are distinct in a unique index, so platform accounts need their own one.
            models.UniqueConstraint(
                fields=["code", "currency"],
                condition=Q(merchant__isnull=True),
                name="ledger_unique_platform_account",
            ),
        ]

    def __str__(self):
        owner = self.merchant_id or "platform"
        return f"{self.code}:{self.currency}:{owner}"

    def balance(self):
        zero = models.Value(0, output_field=models.BigIntegerField())
        totals = self.entries.aggregate(
            debits=Coalesce(Sum("amount", filter=Q(direction=Direction.DEBIT)), zero),
            credits=Coalesce(Sum("amount", filter=Q(direction=Direction.CREDIT)), zero),
        )
        if self.normal_side == Direction.DEBIT:
            return totals["debits"] - totals["credits"]
        return totals["credits"] - totals["debits"]


class LedgerTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=80, db_index=True)
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} ({self.description})"


class LedgerEntry(models.Model):
    transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.PROTECT, related_name="entries"
    )
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="entries")
    direction = models.CharField(max_length=6, choices=Direction.choices)
    amount = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ledger_entry_amount_positive")
        ]

    def __str__(self):
        return f"{self.direction} {self.amount} {self.account}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Ledger entries are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Ledger entries are immutable.")
