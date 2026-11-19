from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction

from ledger import services as ledger
from payments import cards
from payments.models import Payment


def compute_fee(amount):
    variable = (Decimal(amount) * settings.PAYFLOW_FEE_PERCENT / 100).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    return int(variable) + settings.PAYFLOW_FEE_FIXED


def create_payment(*, merchant, amount, currency, card, description="", metadata=None):
    number = card["number"]
    result = cards.simulate_charge(number, card["exp_month"], card["exp_year"])

    payment = Payment(
        merchant=merchant,
        amount=amount,
        currency=currency,
        description=description,
        metadata=metadata or {},
        card_brand=cards.detect_brand(number),
        card_last4=number[-4:],
        card_exp_month=card["exp_month"],
        card_exp_year=card["exp_year"],
    )

    with transaction.atomic():
        if result.approved:
            payment.status = Payment.Status.SUCCEEDED
            payment.fee = compute_fee(amount)
            payment.save()
            ledger.record_charge(
                merchant=merchant,
                currency=currency,
                amount=amount,
                fee=payment.fee,
                reference=f"payment:{payment.id}",
            )
        else:
            payment.status = Payment.Status.FAILED
            payment.failure_code = result.decline_code
            payment.failure_message = result.message
            payment.save()
    return payment
