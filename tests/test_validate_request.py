from idempy.core import Core
from pytest import fixture

@fixture
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
