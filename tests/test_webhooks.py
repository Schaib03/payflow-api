import json
from unittest import mock

import pytest
import requests
from celery.exceptions import Retry

from webhooks import signing
from webhooks.models import Event, WebhookDelivery, WebhookEndpoint
from webhooks.services import backoff_seconds
from webhooks.tasks import deliver_webhook

from .factories import DECLINED, create_payment

pytestmark = pytest.mark.django_db

ENDPOINT_URL = "https://merchant.example.ma/hooks"


@pytest.fixture
def endpoint(client):
    response = client.post(
        "/v1/webhook-endpoints",
        {"url": ENDPOINT_URL, "enabled_events": ["payment.succeeded", "refund.created"]},
        format="json",
    )
    assert response.status_code == 201
    return response.json()


def fake_response(status_code):
    return mock.Mock(status_code=status_code)


# Signing


def test_signature_roundtrip():
    payload = b'{"id":"evt_1"}'
    header = signing.build_header("whsec_test", payload, timestamp=1_700_000_000)
    assert header.startswith("t=1700000000,v1=")
    assert signing.verify_header(header, payload, "whsec_test", now=1_700_000_100)


@pytest.mark.parametrize(
    ("payload", "secret", "now"),
    [
        (b'{"id":"evt_2"}', "whsec_test", 1_700_000_000),  # body changed
        (b'{"id":"evt_1"}', "whsec_other", 1_700_000_000),  # wrong secret
        (b'{"id":"evt_1"}', "whsec_test", 1_700_000_301),  # too old (replay)
    ],
)
def test_signature_rejected(payload, secret, now):
    header = signing.build_header("whsec_test", b'{"id":"evt_1"}', timestamp=1_700_000_000)
    with pytest.raises(signing.SignatureVerificationError):
        signing.verify_header(header, payload, secret, now=now)


def test_malformed_header_rejected():
    with pytest.raises(signing.SignatureVerificationError):
        signing.verify_header("garbage", b"{}", "whsec_test")


def test_backoff_grows_and_is_capped(settings):
    settings.WEBHOOK_BACKOFF_BASE_SECONDS = 30
    settings.WEBHOOK_BACKOFF_MAX_SECONDS = 600
    assert 30 <= backoff_seconds(1) <= 33
    assert 120 <= backoff_seconds(3) <= 132
    assert 600 <= backoff_seconds(10) <= 660


# Endpoints API


def test_secret_only_returned_on_creation(client, endpoint):
    assert endpoint["secret"].startswith("whsec_")
    listed = client.get("/v1/webhook-endpoints").json()["results"][0]
    assert "secret" not in listed
    assert "secret" not in client.get(f"/v1/webhook-endpoints/{endpoint['id']}").json()


def test_unknown_event_type_rejected(client):
    response = client.post(
        "/v1/webhook-endpoints", {"url": ENDPOINT_URL, "enabled_events": ["nope"]}, format="json"
    )
    assert response.status_code == 400


def test_endpoint_can_be_disabled_and_deleted(client, endpoint):
    url = f"/v1/webhook-endpoints/{endpoint['id']}"
    assert client.patch(url, {"is_active": False}, format="json").json()["is_active"] is False
    assert client.delete(url).status_code == 204
    assert not WebhookEndpoint.objects.exists()


# Events and deliveries


def test_payment_emits_event_and_delivers_signed_payload(
    client, endpoint, django_capture_on_commit_callbacks
):
    with mock.patch("webhooks.services.requests.post", return_value=fake_response(200)) as post:
        with django_capture_on_commit_callbacks(execute=True):
            payment = create_payment(client).json()

    event = Event.objects.get(type="payment.succeeded")
    assert event.data["id"] == payment["id"]

    delivery = WebhookDelivery.objects.get()
    assert delivery.status == "succeeded"
    assert delivery.attempts == 1

    args, kwargs = post.call_args
    assert args[0] == ENDPOINT_URL
    body = kwargs["data"]
    assert json.loads(body)["type"] == "payment.succeeded"
    header = kwargs["headers"]["PayFlow-Signature"]
    assert signing.verify_header(header, body, endpoint["secret"])


def test_unsubscribed_events_are_recorded_but_not_delivered(
    client, endpoint, django_capture_on_commit_callbacks
):
    with mock.patch("webhooks.services.requests.post") as post:
        with django_capture_on_commit_callbacks(execute=True):
            create_payment(client, number=DECLINED)
    assert Event.objects.filter(type="payment.failed").exists()
    assert not WebhookDelivery.objects.exists()
    post.assert_not_called()


def run_like_a_worker(delivery_id, max_runs=20):
    """Call the task again each time it asks for a retry, ignoring the countdown."""
    retries = []
    for _ in range(max_runs):
        try:
            deliver_webhook(delivery_id)
            return retries
        except Retry as retry:
            retries.append(retry)
    raise AssertionError("task never stopped retrying")


def test_failed_delivery_is_retried_then_marked_failed(client, endpoint, settings):
    settings.WEBHOOK_MAX_ATTEMPTS = 4
    create_payment(client)
    delivery = WebhookDelivery.objects.get()

    with mock.patch("webhooks.services.requests.post", return_value=fake_response(500)) as post:
        retries = run_like_a_worker(str(delivery.id))

    delivery.refresh_from_db()
    assert post.call_count == 4
    assert len(retries) == 3
    assert delivery.attempts == 4
    assert delivery.status == "failed"
    assert delivery.last_status_code == 500


def test_delivery_recovers_after_network_error(client, endpoint):
    create_payment(client)
    delivery = WebhookDelivery.objects.get()

    responses = [requests.ConnectionError("refused"), fake_response(503), fake_response(204)]
    with mock.patch("webhooks.services.requests.post", side_effect=responses):
        run_like_a_worker(str(delivery.id))

    delivery.refresh_from_db()
    assert delivery.status == "succeeded"
    assert delivery.attempts == 3
    assert delivery.next_attempt_at is None


def test_refund_event_and_events_api(client, endpoint, django_capture_on_commit_callbacks):
    with mock.patch("webhooks.services.requests.post", return_value=fake_response(200)):
        with django_capture_on_commit_callbacks(execute=True):
            payment = create_payment(client).json()
            client.post(f"/v1/payments/{payment['id']}/refunds", {}, format="json")

    events = client.get("/v1/events").json()["results"]
    assert [e["type"] for e in events] == ["refund.created", "payment.succeeded"]
    only_refunds = client.get("/v1/events?type=refund.created").json()["results"]
    assert len(only_refunds) == 1

    deliveries = client.get(f"/v1/webhook-endpoints/{endpoint['id']}/deliveries").json()
    assert {d["event_type"] for d in deliveries["results"]} == {
        "refund.created",
        "payment.succeeded",
    }


def test_no_delivery_when_transaction_rolls_back(client, endpoint):
    # Without executing on_commit callbacks (as after a rollback) nothing is sent.
    with mock.patch("webhooks.services.requests.post") as post:
        create_payment(client)
    post.assert_not_called()
    assert WebhookDelivery.objects.get().status == "pending"


def test_events_are_scoped_to_merchant(client, other_client):
    create_payment(client)
    assert other_client.get("/v1/events").json()["results"] == []
