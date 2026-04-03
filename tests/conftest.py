import pytest
from idempy.models import Request

@pytest.fixture
def mock_request():
    return Request(
        idempotency_key="test",
        fingerprint="test",
        method="GET",
        path="/",
        url="https://example.com",
    )

@pytest.fixture
def mock_redis():
    return mock_request()