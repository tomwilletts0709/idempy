import pytest
from idempy.base import BaseStore
from idempy.models import IdempotencyKey, Status


# ── Verify BaseStore cannot be instantiated directly ──────────────────────────

def test_base_store_is_abstract():
    with pytest.raises(TypeError):
        BaseStore()


def test_partial_implementation_raises_type_error():
    """A subclass that omits any abstract method cannot be instantiated."""
    class PartialStore(BaseStore):
        def get(self, key):
            return None
        # missing: create_in_progress, mark_completed, mark_failed, delete

    with pytest.raises(TypeError):
        PartialStore()


# ── Minimal concrete implementation used for contract tests ───────────────────

class StubStore(BaseStore):
    """Minimal in-memory implementation that satisfies the BaseStore contract."""

    def __init__(self):
        self._store: dict[str, IdempotencyKey] = {}

    def get(self, key: str) -> IdempotencyKey | None:
        return self._store.get(key)

    def create_in_progress(self, key: str, fingerprint: str) -> bool:
        from datetime import datetime
        if key in self._store:
            return False
        self._store[key] = IdempotencyKey(
            key=key,
            fingerprint=fingerprint,
            status=Status.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        return True

    def mark_completed(self, key, fingerprint, result_data, result_status) -> bool:
        from datetime import datetime
        record = self._store.get(key)
        if record is None or record.fingerprint != fingerprint:
            return False
        self._store[key] = IdempotencyKey(
            key=key, fingerprint=fingerprint, status=Status.SUCCESS,
            created_at=record.created_at, updated_at=datetime.now(),
            result_data=result_data, result_status=result_status,
        )
        return True

    def mark_failed(self, key, fingerprint, result_error) -> bool:
        from datetime import datetime
        record = self._store.get(key)
        if record is None or record.fingerprint != fingerprint:
            return False
        self._store[key] = IdempotencyKey(
            key=key, fingerprint=fingerprint, status=Status.FAILED,
            created_at=record.created_at, updated_at=datetime.now(),
            result_error=result_error,
        )
        return True

    def delete(self, key: str) -> bool:
        if key not in self._store:
            return False
        del self._store[key]
        return True


@pytest.fixture
def store():
    return StubStore()


# ── BaseStore contract tests ───────────────────────────────────────────────────

def test_get_missing_returns_none(store):
    assert store.get("nonexistent") is None


def test_create_in_progress_returns_true_first_call(store):
    assert store.create_in_progress("key-1", "fp-abc") is True


def test_create_in_progress_returns_false_on_duplicate(store):
    store.create_in_progress("key-1", "fp-abc")
    assert store.create_in_progress("key-1", "fp-abc") is False


def test_get_after_create_returns_pending(store):
    store.create_in_progress("key-1", "fp-abc")
    record = store.get("key-1")
    assert record is not None
    assert record.status == Status.PENDING
    assert record.fingerprint == "fp-abc"


def test_mark_completed_transitions_status(store):
    store.create_in_progress("key-1", "fp-abc")
    assert store.mark_completed("key-1", "fp-abc", b"ok", 200) is True
    assert store.get("key-1").status == Status.SUCCESS


def test_mark_completed_wrong_fingerprint_returns_false(store):
    store.create_in_progress("key-1", "fp-abc")
    assert store.mark_completed("key-1", "fp-WRONG", b"ok", 200) is False
    assert store.get("key-1").status == Status.PENDING


def test_mark_completed_missing_key_returns_false(store):
    assert store.mark_completed("ghost", "fp-abc", b"ok", 200) is False


def test_mark_failed_transitions_status(store):
    store.create_in_progress("key-1", "fp-abc")
    assert store.mark_failed("key-1", "fp-abc", "timeout") is True
    assert store.get("key-1").status == Status.FAILED


def test_mark_failed_wrong_fingerprint_returns_false(store):
    store.create_in_progress("key-1", "fp-abc")
    assert store.mark_failed("key-1", "fp-WRONG", "timeout") is False


def test_delete_existing_returns_true(store):
    store.create_in_progress("key-1", "fp-abc")
    assert store.delete("key-1") is True
    assert store.get("key-1") is None


def test_delete_missing_returns_false(store):
    assert store.delete("nonexistent") is False


def test_all_abstract_methods_are_enforced():
    """Enumerate the five required methods and confirm each is abstract."""
    abstract = {
        m for m, v in vars(BaseStore).items()
        if getattr(v, "__isabstractmethod__", False)
    }
    assert abstract == {"get", "create_in_progress", "mark_completed", "mark_failed", "delete"}
