import json
import pytest

# Minimal Django setup — must happen before any Django imports
import django
from django.conf import settings as django_settings

if not django_settings.configured:
    django_settings.configure(
        DATABASES={},
        INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth"],
        ROOT_URLCONF=__name__,
        MIDDLEWARE=["idempy.django_middleware.IdemMiddleware"],
        SECRET_KEY="test-secret",
        ALLOWED_HOSTS=["testserver", "localhost"],
    )
    django.setup()

from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory
from django.urls import path

from idempy import Core, MemoryStore
from idempy.django_middleware import IdemMiddleware


# ── minimal URL conf (required by ROOT_URLCONF) ──────────────────────────────

def pay_view(request):
    return JsonResponse({"charged": True}, status=200)


def fail_view(request):
    raise RuntimeError("gateway down")


def items_view(request):
    return JsonResponse([], safe=False)


urlpatterns = [
    path("pay", pay_view),
    path("fail", fail_view),
    path("items", items_view),
]


# ── helpers ───────────────────────────────────────────────────────────────────

def make_middleware(view, extra_settings: dict | None = None):
    """Return an IdemMiddleware instance wrapping *view* with a fresh Core."""
    if extra_settings:
        django_settings.IDEMPY = extra_settings
    else:
        if hasattr(django_settings, "IDEMPY"):
            del django_settings.IDEMPY  # type: ignore[attr-defined]

    mw = IdemMiddleware(view)
    mw._core = Core(settings={"stores": {"memory": MemoryStore()}, "default_store": "memory"})
    return mw


HEADERS = {"HTTP_IDEMPOTENCY_KEY": "pay-001", "CONTENT_TYPE": "application/json"}
BODY = json.dumps({"amount": 100}).encode()

factory = RequestFactory()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_first_request_succeeds():
    mw = make_middleware(pay_view)
    request = factory.post("/pay", data=BODY, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": "pay-001"})
    response = mw(request)
    assert response.status_code == 200
    assert json.loads(response.content) == {"charged": True}


def test_replay_returns_cached_response():
    mw = make_middleware(pay_view)
    request = factory.post("/pay", data=BODY, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": "pay-001"})
    mw(request)

    request2 = factory.post("/pay", data=BODY, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": "pay-001"})
    response = mw(request2)
    assert response.status_code == 200
    assert json.loads(response.content) == {"charged": True}


def test_conflict_returns_409():
    mw = make_middleware(pay_view)
    request = factory.post("/pay", data=BODY, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": "pay-001"})
    mw(request)

    different_body = json.dumps({"amount": 999}).encode()
    request2 = factory.post("/pay", data=different_body, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": "pay-001"})
    response = mw(request2)
    assert response.status_code == 409
    assert "conflict" in json.loads(response.content)["error"].lower()


def test_no_header_passes_through():
    mw = make_middleware(pay_view)
    r1 = mw(factory.post("/pay", data=BODY, content_type="application/json"))
    r2 = mw(factory.post("/pay", data=BODY, content_type="application/json"))
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_safe_method_not_gated():
    mw = make_middleware(items_view)
    r1 = mw(factory.get("/items", **{"HTTP_IDEMPOTENCY_KEY": "get-001"}))
    r2 = mw(factory.get("/items", **{"HTTP_IDEMPOTENCY_KEY": "get-001"}))
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_view_exception_propagates():
    mw = make_middleware(fail_view)
    request = factory.post("/fail", data=BODY, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": "fail-001"})
    with pytest.raises(RuntimeError, match="gateway down"):
        mw(request)


def test_custom_header_name():
    mw = make_middleware(pay_view, extra_settings={"header_name": "X-Request-Id"})
    r1 = mw(factory.post("/pay", data=BODY, content_type="application/json", **{"HTTP_X_REQUEST_ID": "req-abc"}))
    r2 = mw(factory.post("/pay", data=BODY, content_type="application/json", **{"HTTP_X_REQUEST_ID": "req-abc"}))
    assert r1.status_code == 200
    assert r2.status_code == 200  # replay
