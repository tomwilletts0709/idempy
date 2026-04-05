import pytest
import fakeredis
from idempy.redis import RedisStore
from idempy.models import Status


@pytest.fixture
def store():
    return RedisStore(fakeredis.FakeRedis())


def test_get_missing_key_returns_none(store):
    assert store.get("nonexistent") is None


def test_create_in_progress_returns_true(store):
    assert store.create_in_progress("pay-001", "fp-abc") is True


def test_create_in_progress_twice_returns_false(store):
    store.create_in_progress("pay-001", "fp-abc")
    assert store.create_in_progress("pay-001", "fp-abc") is False


def test_get_after_create_returns_pending_record(store):
    store.create_in_progress("pay-001", "fp-abc")
    record = store.get("pay-001")
    assert record is not None
    assert record.key == "pay-001"
    assert record.fingerprint == "fp-abc"
    assert record.status == Status.PENDING


def test_mark_completed_transitions_to_success(store):
    store.create_in_progress("pay-001", "fp-abc")
    result = store.mark_completed("pay-001", "fp-abc", b'{"charged": true}', 200)
    assert result is True
    record = store.get("pay-001")
    assert record.status == Status.SUCCESS
    assert record.result_data == b'{"charged": true}'
    assert record.result_status == 200


def test_mark_completed_wrong_fingerprint_returns_false(store):
    store.create_in_progress("pay-001", "fp-abc")
    result = store.mark_completed("pay-001", "fp-WRONG", b"", 200)
    assert result is False
    assert store.get("pay-001").status == Status.PENDING


def test_mark_completed_missing_key_returns_false(store):
    assert store.mark_completed("ghost", "fp-abc", b"", 200) is False


def test_mark_failed_transitions_to_failed(store):
    store.create_in_progress("pay-001", "fp-abc")
    result = store.mark_failed("pay-001", "fp-abc", "gateway timeout")
    assert result is True
    record = store.get("pay-001")
    assert record.status == Status.FAILED
    assert record.result_error == "gateway timeout"


def test_mark_failed_wrong_fingerprint_returns_false(store):
    store.create_in_progress("pay-001", "fp-abc")
    assert store.mark_failed("pay-001", "fp-WRONG", "err") is False


def test_delete_existing_key_returns_true(store):
    store.create_in_progress("pay-001", "fp-abc")
    assert store.delete("pay-001") is True
    assert store.get("pay-001") is None


def test_delete_missing_key_returns_false(store):
    assert store.delete("nonexistent") is False


def test_key_prefix_namespaces_keys():
    r = fakeredis.FakeRedis()
    store_a = RedisStore(r, key_prefix="app_a:")
    store_b = RedisStore(r, key_prefix="app_b:")

    store_a.create_in_progress("pay-001", "fp-abc")

    assert store_a.get("pay-001") is not None
    assert store_b.get("pay-001") is None  # different namespace


def test_full_lifecycle(store):
    # create
    assert store.create_in_progress("pay-001", "fp-abc") is True
    assert store.get("pay-001").status == Status.PENDING

    # complete
    store.mark_completed("pay-001", "fp-abc", b"ok", 200)
    assert store.get("pay-001").status == Status.SUCCESS

    # delete
    store.delete("pay-001")
    assert store.get("pay-001") is None
