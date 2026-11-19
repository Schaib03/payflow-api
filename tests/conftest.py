import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from config.celery import app as celery_app


@pytest.fixture(autouse=True)
def _isolated_environment():
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


def signup(client, name="Atlas Shop", email="owner@atlas.ma"):
    response = client.post("/v1/merchants", {"name": name, "email": email}, format="json")
    assert response.status_code == 201, response.content
    return response.json()


@pytest.fixture
def merchant_data(api_client):
    return signup(api_client)


@pytest.fixture
def client(merchant_data):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {merchant_data['api_key']}")
    return client


@pytest.fixture
def other_client():
    data = signup(APIClient(), name="Other Store", email="other@store.ma")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['api_key']}")
    return client
