import datetime
import re

from rest_framework import serializers

from payments import cards
from payments.models import Currency, Payment, Refund

MIN_AMOUNT = 500  # 5.00 in any supported currency; keeps fees below the amount
MAX_AMOUNT = 100_000_000
CVC_RE = re.compile(r"^\d{3,4}$")


class CardInputSerializer(serializers.Serializer):
    number = serializers.CharField(write_only=True, max_length=23)
    exp_month = serializers.IntegerField(min_value=1, max_value=12)
    exp_year = serializers.IntegerField(min_value=2000, max_value=2100)
    cvc = serializers.CharField(write_only=True, max_length=4)

    def validate_number(self, value):
        number = cards.normalize_number(value)
        if not cards.luhn_valid(number):
            raise serializers.ValidationError("Card number is invalid.", code="invalid_number")
        return number

    def validate_cvc(self, value):
        if not CVC_RE.match(value):
            raise serializers.ValidationError("CVC must be 3 or 4 digits.", code="invalid_cvc")
        return value

    def validate_exp_year(self, value):
        if value > datetime.date.today().year + 20:
            raise serializers.ValidationError("Expiry year is too far in the future.")
        return value


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(
        min_value=MIN_AMOUNT,
        max_value=MAX_AMOUNT,
        help_text="Amount in minor units, e.g. 15000 = 150.00 MAD.",
    )
    currency = serializers.ChoiceField(choices=Currency.choices)
    card = CardInputSerializer()
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    metadata = serializers.DictField(required=False)

    def validate_metadata(self, value):
        if len(value) > 20:
            raise serializers.ValidationError("At most 20 metadata keys.")
        for key, item in value.items():
            if len(str(key)) > 40 or not isinstance(item, str | int | float | bool):
                raise serializers.ValidationError(
                    "Metadata keys are limited to 40 chars and values to scalars."
                )
        return value


class CardOutputSerializer(serializers.Serializer):
    brand = serializers.CharField(source="card_brand")
    last4 = serializers.CharField(source="card_last4")
    exp_month = serializers.IntegerField(source="card_exp_month")
    exp_year = serializers.IntegerField(source="card_exp_year")


class PaymentSerializer(serializers.ModelSerializer):
    card = CardOutputSerializer(source="*", read_only=True)
    refundable_amount = serializers.IntegerField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "currency",
            "status",
            "amount_refunded",
            "refundable_amount",
            "fee",
            "description",
            "metadata",
            "card",
            "failure_code",
            "failure_message",
            "created_at",
        ]
        read_only_fields = fields


class RefundCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(
        min_value=1, required=False, help_text="Defaults to the remaining refundable amount."
    )
    reason = serializers.ChoiceField(choices=Refund.Reason.choices, required=False)


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ["id", "payment", "amount", "currency", "reason", "created_at"]
        read_only_fields = fields
