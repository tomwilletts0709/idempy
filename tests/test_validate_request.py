import pytest

from idempy.core import Core
from idempy.models import BeginAction


@pytest.fixture
def core():
    return Core()


def test_validate_request(core):
    request = {
        'idempotency_key': '1234567890',
        'fingerprint': '1234567890',
    }
    assert core.validate_request(request) is True

def test_validate_request_failure(core): 
    request = {
        'idempotency_key': None,
        'fingerprint': '1234567890',
    }
    assert core.validate_request(request) is False

def test_validate_fingerprint(core):
    fingerprint = '1234567890'
    assert core.validate_fingerprint(fingerprint) is True

def test_validate_fingerprint_failure(core):
    fingerprint = None
    assert core.validate_fingerprint(fingerprint) is False

def test_missing_idempotency_key(core):
    request = {
        'fingerprint': '1234567890',
    }
    assert core.validate_request(request) is False


def test_begin(core):
    request = {
        "idempotency_key": "1234567890",
        "fingerprint": "1234567890",
    }
    result = core.begin(request)
    assert result.action == BeginAction.SUCCESS
    assert result.record is not None


def test_begin_replay_same_request(core):
    request = {
        "idempotency_key": "replay-key",
        "fingerprint": "same-fingerprint",
    }
    first = core.begin(request)
    assert first.action == BeginAction.SUCCESS
    second = core.begin(request)
    assert second.action == BeginAction.REPLAY

