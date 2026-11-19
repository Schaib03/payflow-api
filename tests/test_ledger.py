import pytest
from django.core.management import call_command

from ledger import services
from ledger.models import Direction, LedgerAccount, LedgerEntry
from merchants.models import Merchant

pytestmark = pytest.mark.django_db

Code = LedgerAccount.Code


@pytest.fixture
def merchant():
    return Merchant.objects.create(name="Shop", email="shop@example.ma")


def test_unbalanced_transaction_is_rejected(merchant):
    clearing = services.get_account(Code.PROCESSOR_CLEARING, "MAD")
    balance = services.get_account(Code.MERCHANT_BALANCE, "MAD", merchant)
    with pytest.raises(services.UnbalancedTransaction):
        services.post_transaction(
            description="bad",
            reference="test",
            legs=[
                services.Leg(clearing, Direction.DEBIT, 1000),
                services.Leg(balance, Direction.CREDIT, 900),
            ],
        )
    assert LedgerEntry.objects.count() == 0


def test_mixed_currencies_rejected(merchant):
    with pytest.raises(services.UnbalancedTransaction):
        services.post_transaction(
            description="bad",
            reference="test",
            legs=[
                services.Leg(
                    services.get_account(Code.PROCESSOR_CLEARING, "MAD"), Direction.DEBIT, 10
                ),
                services.Leg(
                    services.get_account(Code.MERCHANT_BALANCE, "EUR", merchant),
                    Direction.CREDIT,
                    10,
                ),
            ],
        )


def test_charge_then_refund_balances(merchant):
    services.record_charge(merchant=merchant, currency="MAD", amount=10000, fee=250, reference="p1")
    services.record_refund(merchant=merchant, currency="MAD", amount=4000, reference="r1")

    assert services.get_account(Code.MERCHANT_BALANCE, "MAD", merchant).balance() == 5750
    assert services.get_account(Code.PLATFORM_FEES, "MAD").balance() == 250
    assert services.get_account(Code.PROCESSOR_CLEARING, "MAD").balance() == 6000
    call_command("verify_ledger")


def test_platform_accounts_are_unique():
    first = services.get_account(Code.PLATFORM_FEES, "USD")
    second = services.get_account(Code.PLATFORM_FEES, "USD")
    assert first.pk == second.pk


def test_entries_are_immutable(merchant):
    services.record_charge(merchant=merchant, currency="EUR", amount=1000, fee=0, reference="p")
    entry = LedgerEntry.objects.first()
    entry.amount = 1
    with pytest.raises(ValueError):
        entry.save()
    with pytest.raises(ValueError):
        entry.delete()
