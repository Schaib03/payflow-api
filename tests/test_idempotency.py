from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.idempotency import request_fingerprint
from core.models import IdempotencyKey
from payments.models import Payment

from .factories import DECLINED, create_payment, payment_payload

pytestmark = pytest.mark.django_db


def key(value):
    return {"Idempotency-Key": value}


def test_replay_returns_stored_response_without_second_charge(client):
    first = create_payment(client, headers=key("order-1042"))
    second = create_payment(client, headers=key("order-1042"))

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert second["Idempotent-Replayed"] == "true"
    assert "Idempotent-Replayed" not in first
    assert Payment.objects.count() == 1


def test_same_key_different_body_is_422(client):
    create_payment(client, amount=15000, headers=key("k1"))
    response = create_payment(client, amount=99900, headers=key("k1"))
    assert response.status_code == 422
    assert response.json()["error"] == {
        "type": "idempotency_error",
        "code": "idempotency_key_reused",
        "message": "This Idempotency-Key was already used with a different request.",
    }
    assert Payment.objects.count() == 1


def test_failed_validation_releases_the_key(client):
    bad = create_payment(client, amount=1, headers=key("k2"))
    assert bad.status_code == 400
    assert not IdempotencyKey.objects.exists()

    good = create_payment(client, headers=key("k2"))
    assert good.status_code == 201


def test_declined_payment_is_replayed(client):
    first = create_payment(client, number=DECLINED, headers=key("k3"))
    second = create_payment(client, number=DECLINED, headers=key("k3"))
    assert first.status_code == second.status_code == 402
    assert first.json() == second.json()
    assert Payment.objects.count() == 1


def test_keys_are_scoped_per_merchant(client, other_client):
    create_payment(client, headers=key("shared"))
    response = create_payment(other_client, amount=70000, headers=key("shared"))
    assert response.status_code == 201
    assert Payment.objects.count() == 2


def test_in_progress_key_is_409(client, merchant_data):
    # Simulates a concurrent request that claimed the key and has not finished yet.
    same_request = SimpleNamespace(method="POST", path="/v1/payments", data=payment_payload())
    IdempotencyKey.objects.create(
        merchant_id=merchant_data["id"],
        key="busy",
        request_fingerprint=request_fingerprint(same_request),
    )
    response = create_payment(client, headers=key("busy"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_key_in_progress"
    assert Payment.objects.count() == 0


def test_card_number_not_stored_in_idempotency_record(client):
    create_payment(client, headers=key("k4"))
    record = IdempotencyKey.objects.get()
    assert "4242424242424242" not in str(record.response_body)
    assert len(record.request_fingerprint) == 64


def test_expired_keys_are_reusable_and_purged(client):
    create_payment(client, headers=key("old"))
    IdempotencyKey.objects.update(created_at=timezone.now() - timedelta(days=2))

    response = create_payment(client, amount=80000, headers=key("old"))
    assert response.status_code == 201

    IdempotencyKey.objects.update(created_at=timezone.now() - timedelta(days=2))
    call_command("purge_idempotency_keys")
    assert not IdempotencyKey.objects.exists()


def test_overlong_key_rejected(client):
    response = create_payment(client, headers=key("x" * 256))
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()["error"]["fields"]
