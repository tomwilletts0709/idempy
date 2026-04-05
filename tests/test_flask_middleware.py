import json
import pytest
from flask import Flask, jsonify
from idempy.flask_middleware import IdemMiddleware


@pytest.fixture
def app():
    from idempy import Core, MemoryStore
    app = Flask(__name__)
    IdemMiddleware(app, core=Core(settings={"stores": {"memory": MemoryStore()}, "default_store": "memory"}))

    @app.route("/pay", methods=["POST"])
    def pay():
        return jsonify({"charged": True}), 200

    @app.route("/fail", methods=["POST"])
    def fail_route():
        raise RuntimeError("payment gateway down")

    @app.route("/items", methods=["GET"])
    def items():
        return jsonify([]), 200

    return app


@pytest.fixture
def client(app):
    return app.test_client()


HEADERS = {"Idempotency-Key": "pay-001", "Content-Type": "application/json"}
BODY = json.dumps({"amount": 100}).encode()


def test_first_request_succeeds(client):
    response = client.post("/pay", data=BODY, headers=HEADERS)
    assert response.status_code == 200
    assert response.get_json() == {"charged": True}


def test_replay_returns_cached_response(client):
    client.post("/pay", data=BODY, headers=HEADERS)
    # Second request with same key + body — should replay
    response = client.post("/pay", data=BODY, headers=HEADERS)
    assert response.status_code == 200
    assert response.get_json() == {"charged": True}


def test_conflict_returns_409(client):
    client.post("/pay", data=BODY, headers=HEADERS)
    # Same key, different body → different fingerprint → conflict
    different_body = json.dumps({"amount": 999}).encode()
    response = client.post("/pay", data=different_body, headers=HEADERS)
    assert response.status_code == 409
    assert "conflict" in response.get_json()["error"].lower()


def test_no_header_passes_through(client):
    # No Idempotency-Key header — request runs normally every time
    r1 = client.post("/pay", data=BODY, content_type="application/json")
    r2 = client.post("/pay", data=BODY, content_type="application/json")
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_safe_method_not_gated(client):
    # GET requests are never intercepted even with the header
    r1 = client.get("/items", headers={"Idempotency-Key": "get-001"})
    r2 = client.get("/items", headers={"Idempotency-Key": "get-001"})
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_view_exception_marks_record_failed(app):
    """An unhandled view exception should fail the record, not complete it."""
    client = app.test_client()
    app.config["PROPAGATE_EXCEPTIONS"] = False
    headers = {"Idempotency-Key": "fail-001", "Content-Type": "application/json"}
    response = client.post("/fail", data=BODY, headers=headers)
    assert response.status_code == 500


def test_custom_header_name():
    app = Flask(__name__)
    IdemMiddleware(app, header_name="X-Request-Id")

    @app.route("/pay", methods=["POST"])
    def pay():
        return jsonify({"ok": True}), 200

    client = app.test_client()
    headers = {"X-Request-Id": "req-abc", "Content-Type": "application/json"}
    r1 = client.post("/pay", data=BODY, headers=headers)
    r2 = client.post("/pay", data=BODY, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200  # replay
