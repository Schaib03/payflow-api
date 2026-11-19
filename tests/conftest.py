import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _isolated_environment(settings):
    # Celery is configured with namespace="CELERY" from the Django settings object,
    # so tasks run inline when the CELERY_* settings say so.
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
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
