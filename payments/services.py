from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction

from core.exceptions import InvalidRequest
from ledger import services as ledger
from payments import cards
from payments.models import Payment, Refund


class RefundNotAllowed(InvalidRequest):
    default_code = "refund_not_allowed"
    default_detail = "This payment cannot be refunded."


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


def refund_payment(*, merchant, payment_id, amount=None, reason=""):
    """Refund all or part of a payment.

    The payment row is locked (SELECT ... FOR UPDATE) for the whole transaction so two
    concurrent refunds cannot both read the same refundable amount and over-refund.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id, merchant=merchant)

        refundable = payment.refundable_amount
        if refundable == 0:
            raise RefundNotAllowed("This payment has nothing left to refund.")
        if amount is None:
            amount = refundable
        if amount > refundable:
            raise RefundNotAllowed(f"Amount exceeds the refundable amount ({refundable}).")

        refund = Refund.objects.create(
            payment=payment, amount=amount, currency=payment.currency, reason=reason
        )
        payment.amount_refunded += amount
        payment.status = (
            Payment.Status.REFUNDED
            if payment.amount_refunded == payment.amount
            else Payment.Status.PARTIALLY_REFUNDED
        )
        payment.save(update_fields=["amount_refunded", "status", "updated_at"])
        ledger.record_refund(
            merchant=merchant,
            currency=payment.currency,
            amount=amount,
            reference=f"refund:{refund.id}",
        )
    return refund
