import pytest
from django.core.management import call_command

from core.throttling import MerchantRateThrottle, SignupRateThrottle

from .factories import create_payment

pytestmark = pytest.mark.django_db


def test_merchant_rate_limit(client, monkeypatch):
    monkeypatch.setattr(MerchantRateThrottle, "rate", "3/min", raising=False)
    statuses = [client.get("/v1/payments").status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]

    response = client.get("/v1/payments")
    error = response.json()["error"]
    assert error["type"] == "rate_limit_error"
    assert error["retry_after"] > 0
    assert "Retry-After" in response


def test_rate_limit_is_per_merchant(client, other_client, monkeypatch):
    monkeypatch.setattr(MerchantRateThrottle, "rate", "1/min", raising=False)
    assert client.get("/v1/payments").status_code == 200
    assert client.get("/v1/payments").status_code == 429
    assert other_client.get("/v1/payments").status_code == 200


def test_signup_rate_limit(api_client, monkeypatch):
    monkeypatch.setattr(SignupRateThrottle, "rate", "2/hour", raising=False)
    codes = [
        api_client.post(
            "/v1/merchants", {"name": "S", "email": f"s{i}@shop.ma"}, format="json"
        ).status_code
        for i in range(3)
    ]
    assert codes == [201, 201, 429]


def test_openapi_schema_and_docs(api_client):
    schema = api_client.get("/v1/schema")
    assert schema.status_code == 200
    assert b"/v1/payments/{id}/refunds" in schema.content
    assert b"Idempotency-Key" in schema.content
    assert api_client.get("/docs").status_code == 200


def test_schema_generates_without_warnings(tmp_path):
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", tmp_path / "s.yaml")


def test_business_metrics(client, api_client):
    create_payment(client, currency="USD")
    body = api_client.get("/metrics").content.decode()
    assert 'payflow_payments_total{currency="USD",status="succeeded"}' in body


def test_wrong_method_uses_error_format(client):
    response = client.delete("/v1/payments")
    assert response.status_code == 405
    assert response.json()["error"]["type"] == "invalid_request_error"


def test_non_json_body_is_rejected(client):
    response = client.post("/v1/payments", "amount=1", content_type="text/plain")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"
