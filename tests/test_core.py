from idempy.core import Core
from idempy.models import Request, Status, BeginAction, ReplayAction
from idempy.memory import MemoryStore
import pytest



@pytest.fixture
def core(): 
    return Core(settings={"stores": {"memory": MemoryStore()}})

def test_complete(core):
    begin = core.begin(Request(
    idempotency_key="test", 
    fingerprint="test",
    method="GET",
    path="/",
    url="https://example.com",
    headers={},
    body=b"",
    query_params={},
    path_params={},
    cookies={},
    json={}))
    assert begin.action == BeginAction.SUCCESS
    complete = core.complete(
        record=begin.record,
        result_data = b"", 
        result_status = 200,
    )
    assert complete is Status.SUCCESS

def test_fail(core): 
    begin = core.begin(Request(
    idempotency_key="test", 
    fingerprint="test",
    method="GET",
    path="/",
    url="https://example.com",
    headers={},
    body=b"",
    query_params={},
    path_params={},
    cookies={},
    json={}))
    assert begin.action == BeginAction.SUCCESS
    fail = core.fail(
        record=begin.record,
        result_error = "Error",
    )
    assert fail is Status.FAILED

def test_get_status(core):
    begin = core.begin(Request(
    idempotency_key="test", 
    fingerprint="test",
    method="GET",
    path="/",
    url="https://example.com",
    headers={},
    body=b"",
    query_params={},
    path_params={},
    cookies={},
    json={}))
    assert begin.action == BeginAction.SUCCESS
    get_status = core.get_status(begin.record.request)
    assert get_status is Status.PENDING

def test_replay(core):
    begin = core.begin(Request(
    idempotency_key="test", 
    fingerprint="test",
    method="GET",
    path="/",
    url="https://example.com",
    headers={},
    body=b"",
    query_params={},
    path_params={},
    cookies={},
    json={}))
    assert begin.action == BeginAction.SUCCESS
    replay = core.replay(begin.record.request)
    assert replay.action == ReplayAction.SUCCESS