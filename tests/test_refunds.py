import pytest
from django.core.management import call_command

from ledger.models import Direction, LedgerEntry
from payments.models import Payment
from payments.services import compute_fee

from .factories import DECLINED, create_payment

pytestmark = pytest.mark.django_db


@pytest.fixture
def payment(client):
    return create_payment(client, amount=10000).json()


def refund(client, payment_id, headers=None, **body):
    return client.post(
        f"/v1/payments/{payment_id}/refunds", body, format="json", headers=headers or {}
    )


def test_partial_then_full_refund(client, payment):
    first = refund(client, payment["id"], amount=3000, reason="requested_by_customer")
    assert first.status_code == 201
    assert first.json()["amount"] == 3000

    detail = client.get(f"/v1/payments/{payment['id']}").json()
    assert detail["status"] == "partially_refunded"
    assert detail["refundable_amount"] == 7000

    second = refund(client, payment["id"])
    assert second.json()["amount"] == 7000
    assert Payment.objects.get().status == "refunded"

    listed = client.get(f"/v1/payments/{payment['id']}/refunds").json()["results"]
    assert len(listed) == 2


def test_refund_cannot_exceed_remaining(client, payment):
    refund(client, payment["id"], amount=6000)
    response = refund(client, payment["id"], amount=5000)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "refund_not_allowed"
    assert "4000" in error["message"]


def test_fully_refunded_payment_rejects_more(client, payment):
    refund(client, payment["id"])
    response = refund(client, payment["id"], amount=1)
    assert response.status_code == 400


def test_failed_payment_cannot_be_refunded(client):
    payment_id = create_payment(client, number=DECLINED).json()["error"]["payment"]
    assert refund(client, payment_id).status_code == 400


def test_refund_ledger_and_balance(client, payment):
    refund(client, payment["id"], amount=2500)
    entries = LedgerEntry.objects.filter(transaction__reference__startswith="refund:")
    assert {(e.account.code, e.direction, e.amount) for e in entries} == {
        ("merchant_balance", Direction.DEBIT, 2500),
        ("processor_clearing", Direction.CREDIT, 2500),
    }
    balance = client.get("/v1/balance").json()["balances"][0]["available"]
    assert balance == 10000 - compute_fee(10000) - 2500
    call_command("verify_ledger")


def test_refund_other_merchants_payment_is_404(other_client, payment):
    assert refund(other_client, payment["id"]).status_code == 404


def test_refund_is_idempotent(client, payment):
    headers = {"Idempotency-Key": "refund-1"}
    first = refund(client, payment["id"], headers=headers, amount=1000)
    second = refund(client, payment["id"], headers=headers, amount=1000)
    assert first.json() == second.json()
    assert Payment.objects.get().amount_refunded == 1000
