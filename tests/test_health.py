import pytest

pytestmark = pytest.mark.django_db


def test_health_checks_database(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_liveness(api_client):
    assert api_client.get("/health/live").status_code == 200


def test_metrics_exposed(api_client):
    api_client.get("/health")
    response = api_client.get("/metrics")
    assert response.status_code == 200
    assert b"django_http_requests_total_by_method_total" in response.content


def test_unknown_route_uses_error_format(api_client):
    response = api_client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found_error"


def test_request_id_is_echoed(api_client):
    response = api_client.get("/health/live", HTTP_X_REQUEST_ID="abc-123")
    assert response["X-Request-Id"] == "abc-123"
