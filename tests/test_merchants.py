import pytest
from rest_framework.test import APIClient

from merchants.models import ApiKey

pytestmark = pytest.mark.django_db


def test_signup_returns_key_once_and_stores_only_hash(merchant_data):
    raw_key = merchant_data["api_key"]
    assert raw_key.startswith("sk_test_")

    stored = ApiKey.objects.get()
    assert stored.key_hash == ApiKey.hash_key(raw_key)
    assert raw_key not in (stored.key_hash, stored.prefix)
    assert stored.prefix == raw_key[:12]


def test_me_with_valid_key(client, merchant_data):
    response = client.get("/v1/merchants/me")
    assert response.status_code == 200
    assert response.json()["id"] == merchant_data["id"]
    assert "api_key" not in response.json()


def test_missing_key_is_401_with_error_format(api_client):
    response = api_client.get("/v1/merchants/me")
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"
    error = response.json()["error"]
    assert error["type"] == "authentication_error"
    assert error["code"] == "not_authenticated"


def test_invalid_key_rejected(merchant_data):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer sk_test_wrong")
    response = client.get("/v1/merchants/me")
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid API key."


def test_revoked_key_rejected(client):
    ApiKey.objects.update(revoked_at="2026-01-01T00:00:00Z")
    assert client.get("/v1/merchants/me").status_code == 401


def test_duplicate_email_is_validation_error(api_client, merchant_data):
    response = api_client.post(
        "/v1/merchants", {"name": "Copy", "email": merchant_data["email"]}, format="json"
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "email" in error["fields"]
