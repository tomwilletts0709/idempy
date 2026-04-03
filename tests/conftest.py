import pytest
from idempy.models import Request

@pytest.fixture
mock_request():
    return Request(
        idempotency_key="test",
        fingerprint="test",
        method="GET",
        path="/",
        url="https://example.com",
    )

@pytest.fixture
mock_redis()
    return mock_request()