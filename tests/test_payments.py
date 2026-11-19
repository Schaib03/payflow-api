from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db.models import Sum

from ledger.models import Direction, LedgerEntry
from payments.models import Payment
from payments.services import compute_fee

from .factories import DECLINED, INSUFFICIENT_FUNDS, MASTERCARD_OK, create_payment

pytestmark = pytest.mark.django_db


def test_fee_is_percentage_plus_fixed(settings):
    settings.PAYFLOW_FEE_PERCENT = Decimal("1.5")
    settings.PAYFLOW_FEE_FIXED = 100
    assert compute_fee(15000) == 325  # 225 + 100
    assert compute_fee(1033) == 115  # 15.495 -> 15
    assert compute_fee(1100) == 117  # 16.5 -> 17, half up


def test_successful_payment(client):
    response = create_payment(client, number=MASTERCARD_OK)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["card"] == {
        "brand": "mastercard",
        "last4": "4444",
        "exp_month": 12,
        "exp_year": 2030,
    }
    assert body["refundable_amount"] == 15000
    assert "number" not in body["card"]


def test_full_card_number_is_never_stored(client):
    create_payment(client)
    payment = Payment.objects.get()
    stored = " ".join(str(value) for value in payment.__dict__.values())
    assert "4242424242424242" not in stored
    assert payment.card_last4 == "4242"


def test_payment_writes_balanced_ledger(client):
    create_payment(client, amount=20000)
    payment = Payment.objects.get()
    entries = LedgerEntry.objects.filter(transaction__reference=f"payment:{payment.id}")
    debits = entries.filter(direction=Direction.DEBIT).aggregate(total=Sum("amount"))["total"]
    credits = entries.filter(direction=Direction.CREDIT).aggregate(total=Sum("amount"))["total"]
    assert debits == credits == 20000
    assert entries.count() == 3
    call_command("verify_ledger")


def test_balance_endpoint(client):
    create_payment(client, amount=10000, currency="MAD")
    create_payment(client, amount=10000, currency="EUR")
    response = client.get("/v1/balance")
    fee = compute_fee(10000)
    assert response.json() == {
        "balances": [
            {"currency": "EUR", "available": 10000 - fee},
            {"currency": "MAD", "available": 10000 - fee},
        ]
    }


@pytest.mark.parametrize(
    ("number", "code"), [(DECLINED, "card_declined"), (INSUFFICIENT_FUNDS, "insufficient_funds")]
)
def test_declined_payment_returns_402(client, number, code):
    response = create_payment(client, number=number)
    assert response.status_code == 402
    error = response.json()["error"]
    assert error["type"] == "card_error"
    assert error["code"] == code
    payment = Payment.objects.get(pk=error["payment"])
    assert payment.status == "failed"
    assert LedgerEntry.objects.count() == 0


def test_invalid_card_number_is_validation_error(client):
    response = create_payment(client, number="4242424242424241")
    assert response.status_code == 400
    assert response.json()["error"]["fields"]["card"]["number"] == ["Card number is invalid."]
    assert Payment.objects.count() == 0


@pytest.mark.parametrize("amount", [499, 0, -100])
def test_amount_lower_bound(client, amount):
    assert create_payment(client, amount=amount).status_code == 400


def test_unsupported_currency(client):
    assert create_payment(client, currency="GBP").status_code == 400


def test_list_and_retrieve_are_scoped_to_merchant(client, other_client):
    payment_id = create_payment(client).json()["id"]
    create_payment(other_client)

    listing = client.get("/v1/payments").json()
    assert [p["id"] for p in listing["results"]] == [payment_id]
    assert client.get(f"/v1/payments/{payment_id}").status_code == 200
    assert other_client.get(f"/v1/payments/{payment_id}").status_code == 404


def test_list_filters_by_status(client):
    create_payment(client)
    create_payment(client, number=DECLINED)
    results = client.get("/v1/payments?status=failed").json()["results"]
    assert len(results) == 1
    assert results[0]["status"] == "failed"
