"""End-to-end lifecycle tests.

Covers two store backends (MemoryStore and RedisStore via fakeredis) to verify
that the Core orchestration layer behaves identically regardless of backend.
"""

import pytest
import fakeredis

from idempy.core import Core
from idempy.memory import MemoryStore
from idempy.redis import RedisStore
from idempy.models import BeginAction, ReplayAction, Request, Status


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_request(idempotency_key: str, fingerprint: str, store: str = "memory") -> Request:
    return Request(
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
        method="POST",
        path="/payments",
        url="https://example.com/payments",
        headers={},
        body=b"",
        query_params={},
        path_params={},
        cookies={},
        json={},
        store=store,
    )


def memory_core() -> Core:
    return Core(settings={"stores": {"memory": MemoryStore()}, "default_store": "memory"})


def redis_core() -> Core:
    backend = RedisStore(fakeredis.FakeRedis())
    return Core(settings={"stores": {"redis": backend}, "default_store": "redis"})


@pytest.fixture(params=["memory", "redis"])
def core_and_store(request):
    """Returns (core, store_name) for both backends."""
    name = request.param
    if name == "memory":
        return memory_core(), "memory"
    return redis_core(), "redis"


# ── Lifecycle tests (run against both backends) ───────────────────────────────

def test_begin_complete_replay_and_status(core_and_store):
    core, store = core_and_store
    req = make_request("pay-001", "fingerprint-abc", store)

    begin_result = core.begin(req)
    assert begin_result.action == BeginAction.SUCCESS
    assert begin_result.record is not None

    record = begin_result.record
    core.complete(record, result_data=b'{"charged": true}', result_status=200)
    assert record.status == Status.SUCCESS

    begin_again = core.begin(req)
    assert begin_again.action == BeginAction.REPLAY

    replay_result = core.replay(req)
    assert replay_result.action == ReplayAction.SUCCESS
    assert replay_result.record is not None

    status = core.get_status(req)
    assert status == Status.SUCCESS


def test_begin_conflict(core_and_store):
    core, store = core_and_store
    req = make_request("pay-002", "fingerprint-abc", store)
    req_different = make_request("pay-002", "fingerprint-xyz", store)

    assert core.begin(req).action == BeginAction.SUCCESS
    assert core.begin(req_different).action == BeginAction.CONFLICT


def test_begin_fail_and_status(core_and_store):
    core, store = core_and_store
    req = make_request("pay-003", "fingerprint-abc", store)

    begin_result = core.begin(req)
    assert begin_result.action == BeginAction.SUCCESS

    record = begin_result.record
    core.fail(record, result_error="Payment gateway timeout")
    assert record.status == Status.FAILED
    assert core.get_status(req) == Status.FAILED


def test_get_status_not_found(core_and_store):
    core, store = core_and_store
    req = make_request("pay-does-not-exist", "fingerprint-abc", store)
    assert core.get_status(req) == Status.NOT_FOUND


def test_replay_not_found(core_and_store):
    core, store = core_and_store
    req = make_request("pay-never-started", "fingerprint-abc", store)
    assert core.replay(req).action == ReplayAction.NOT_FOUND


def test_begin_invalid_request(core_and_store):
    core, _ = core_and_store
    assert core.begin({"idempotency_key": "", "fingerprint": "fp"}).action == BeginAction.INVALID_REQUEST
    assert core.begin({"idempotency_key": "   ", "fingerprint": "fp"}).action == BeginAction.INVALID_REQUEST


# ── Dict input (MemoryStore only — same logic applies to Redis) ───────────────

def test_begin_accepts_dict_input():
    core = memory_core()
    result = core.begin({"idempotency_key": "pay-010", "fingerprint": "fp-abc"})
    assert result.action == BeginAction.SUCCESS


def test_begin_dict_replay():
    core = memory_core()
    core.begin({"idempotency_key": "pay-011", "fingerprint": "fp-abc"})
    result = core.begin({"idempotency_key": "pay-011", "fingerprint": "fp-abc"})
    assert result.action == BeginAction.REPLAY


def test_begin_dict_conflict():
    core = memory_core()
    core.begin({"idempotency_key": "pay-012", "fingerprint": "fp-abc"})
    result = core.begin({"idempotency_key": "pay-012", "fingerprint": "fp-xyz"})
    assert result.action == BeginAction.CONFLICT


# ── Result data round-trip ────────────────────────────────────────────────────

def test_complete_stores_result_data(core_and_store):
    core, store = core_and_store
    req = make_request("pay-020", "fp-abc", store)
    result = core.begin(req)
    core.complete(result.record, result_data=b'{"id": "ch_123"}', result_status=201)

    replay = core.replay(req)
    assert replay.action == ReplayAction.SUCCESS
    assert replay.record.idempotency_key.result_data == b'{"id": "ch_123"}'
    assert replay.record.idempotency_key.result_status == 201


def test_fail_stores_error(core_and_store):
    core, store = core_and_store
    req = make_request("pay-021", "fp-abc", store)
    result = core.begin(req)
    core.fail(result.record, result_error="card_declined")

    # A new begin after failure should replay (key still exists)
    replay = core.begin(req)
    assert replay.action == BeginAction.REPLAY
