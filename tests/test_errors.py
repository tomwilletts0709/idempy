import pytest
from unittest.mock import patch
from pytest.monkeypatch import MonkeyPatch
from idempy.errors import IdempotencyKeyNotFoundError, IdempotencyKeyAlreadyExistsError, IdempotencyKeyInvalidError
from idempy.core import Core
from idempy.models import Request

def test_idempotency_key_not_found_error():
    err = IdempotencyKeyNotFoundError("Idempotency key not found")
    assert str(err) == "Idempotency key not found"
    assert err.idempotency_error == "Idempotency key not found"

def test_idempotency_key_already_exists_error():
    err = IdempotencyKeyAlreadyExistsError("Idempotency key already exists")
    assert str(err) == "Idempotency key already exists"
    assert err.idempotency_error == "Idempotency key already exists"

def test_idempotency_key_invalid_error():
    err = IdempotencyKeyInvalidError("Idempotency key invalid")
    assert str(err) == "Idempotency key invalid"
    assert err.idempotency_error == "Idempotency key invalid"

def test_idempotency_error(monkeypatch):
    def fake_get(): 
        class FakeStores: 
            def raise_for_status(self) -> None: 
                raise IdempotencyKeyNotFoundError("Idempotency key not found")
        return FakeStores()
    monkeypatch.setattr("idempy.core.Core.get_store", fake_get)
    core = Core()
        with pytest.raises(IdempotencyKeyNotFoundError):
            core.get_status(request)