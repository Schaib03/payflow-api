from collections.abc import Sequence
from dataclasses import dataclass

from django.db import transaction

from ledger.models import Direction, LedgerAccount, LedgerEntry, LedgerTransaction

Code = LedgerAccount.Code


class UnbalancedTransaction(Exception):
    pass


@dataclass(frozen=True)
class Leg:
    account: LedgerAccount
    direction: str
    amount: int


def get_account(code, currency, merchant=None):
    account, _ = LedgerAccount.objects.get_or_create(
        code=code,
        currency=currency,
        merchant=merchant,
        defaults={"normal_side": LedgerAccount.NORMAL_SIDES[code]},
    )
    return account


def post_transaction(*, description, reference, legs: Sequence[Leg]):
    if len(legs) < 2:
        raise UnbalancedTransaction("A transaction needs at least two legs.")
    currencies = {leg.account.currency for leg in legs}
    if len(currencies) != 1:
        raise UnbalancedTransaction("All legs must use the same currency.")
    if any(leg.amount <= 0 for leg in legs):
        raise UnbalancedTransaction("Leg amounts must be positive.")

    debits = sum(leg.amount for leg in legs if leg.direction == Direction.DEBIT)
    credits = sum(leg.amount for leg in legs if leg.direction == Direction.CREDIT)
    if debits != credits:
        raise UnbalancedTransaction(f"Debits ({debits}) do not equal credits ({credits}).")

    with transaction.atomic():
        txn = LedgerTransaction.objects.create(
            description=description, reference=reference, currency=currencies.pop()
        )
        LedgerEntry.objects.bulk_create(
            LedgerEntry(
                transaction=txn, account=leg.account, direction=leg.direction, amount=leg.amount
            )
            for leg in legs
        )
    return txn


def record_charge(*, merchant, currency, amount, fee, reference):
    legs = [
        Leg(get_account(Code.PROCESSOR_CLEARING, currency), Direction.DEBIT, amount),
        Leg(get_account(Code.MERCHANT_BALANCE, currency, merchant), Direction.CREDIT, amount - fee),
    ]
    if fee:
        legs.append(Leg(get_account(Code.PLATFORM_FEES, currency), Direction.CREDIT, fee))
    return post_transaction(description="Card charge", reference=reference, legs=legs)


def record_refund(*, merchant, currency, amount, reference):
    # Fees are not refunded.
    legs = [
        Leg(get_account(Code.MERCHANT_BALANCE, currency, merchant), Direction.DEBIT, amount),
        Leg(get_account(Code.PROCESSOR_CLEARING, currency), Direction.CREDIT, amount),
    ]
    return post_transaction(description="Refund", reference=reference, legs=legs)


def merchant_balances(merchant):
    accounts = LedgerAccount.objects.filter(merchant=merchant, code=Code.MERCHANT_BALANCE).order_by(
        "currency"
    )
    return [{"currency": account.currency, "available": account.balance()} for account in accounts]
