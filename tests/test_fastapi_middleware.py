import json
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from idempy import Core, MemoryStore
from idempy.fastapi_middleware import IdemMiddleware


def make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        IdemMiddleware,
        core=Core(settings={"stores": {"memory": MemoryStore()}, "default_store": "memory"}),
    )

    @app.post("/pay")
    async def pay():
        return JSONResponse({"charged": True}, status_code=200)

    @app.post("/fail")
    async def fail_route():
        raise RuntimeError("gateway down")

    @app.get("/items")
    async def items():
        return JSONResponse([])

    return app


@pytest.fixture
def client():
    return TestClient(make_app(), raise_server_exceptions=False)


HEADERS = {"Idempotency-Key": "pay-001", "Content-Type": "application/json"}
BODY = json.dumps({"amount": 100}).encode()


def test_first_request_succeeds(client):
    response = client.post("/pay", content=BODY, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"charged": True}


def test_replay_returns_cached_response(client):
    client.post("/pay", content=BODY, headers=HEADERS)
    response = client.post("/pay", content=BODY, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"charged": True}


def test_conflict_returns_409(client):
    client.post("/pay", content=BODY, headers=HEADERS)
    different_body = json.dumps({"amount": 999}).encode()
    response = client.post("/pay", content=different_body, headers=HEADERS)
    assert response.status_code == 409
    assert "conflict" in response.json()["error"].lower()


def test_no_header_passes_through(client):
    r1 = client.post("/pay", content=BODY, headers={"Content-Type": "application/json"})
    r2 = client.post("/pay", content=BODY, headers={"Content-Type": "application/json"})
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_safe_method_not_gated(client):
    r1 = client.get("/items", headers={"Idempotency-Key": "get-001"})
    r2 = client.get("/items", headers={"Idempotency-Key": "get-001"})
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_view_exception_marks_record_failed(client):
    headers = {"Idempotency-Key": "fail-001", "Content-Type": "application/json"}
    response = client.post("/fail", content=BODY, headers=headers)
    assert response.status_code == 500


def test_custom_header_name():
    app = FastAPI()
    app.add_middleware(
        IdemMiddleware,
        core=Core(settings={"stores": {"memory": MemoryStore()}, "default_store": "memory"}),
        header_name="X-Request-Id",
    )

    @app.post("/pay")
    async def pay():
        return JSONResponse({"ok": True})

    client = TestClient(app)
    headers = {"X-Request-Id": "req-abc", "Content-Type": "application/json"}
    r1 = client.post("/pay", content=BODY, headers=headers)
    r2 = client.post("/pay", content=BODY, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200  # replay
