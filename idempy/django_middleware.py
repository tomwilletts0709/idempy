"""Django middleware for automatic request idempotency.

Add to ``settings.py``::

    MIDDLEWARE = [
        ...
        "idempy.django_middleware.IdemMiddleware",
    ]

Optionally configure via ``settings.py``::

    IDEMPY = {
        "header_name": "Idempotency-Key",   # default
        "safe_methods": {"GET", "HEAD", "OPTIONS"},  # default
        "replay_content_type": "application/json",   # default
    }

To pass a custom ``Core`` instance (e.g. with a Redis store), configure it
before Django starts and assign it to the middleware class directly::

    from idempy.django_middleware import IdemMiddleware
    from idempy import Core

    IdemMiddleware.core = Core(settings={...})

Any request that carries an ``Idempotency-Key`` header (configurable) is gated
through ``Core.begin()``.  Safe methods are skipped.

- **New request** — PENDING record created; view runs; result stored.
- **Replay** — view never called; stored response returned as-is.
- **Conflict** — view never called; 409 returned immediately.
- **No header** — request passes through untouched.
"""

import hashlib
import json
import logging

from django.conf import settings as django_settings
from django.http import HttpRequest, HttpResponse

from idempy.core import Core
from idempy.models import BeginAction
from idempy.models import Request as IdemRequest

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "header_name": "Idempotency-Key",
    "safe_methods": {"GET", "HEAD", "OPTIONS"},
    "replay_content_type": "application/json",
}


class IdemMiddleware:
    """Django middleware for automatic request idempotency.

    Follows the standard Django middleware interface — pass the class path to
    ``MIDDLEWARE`` in ``settings.py``.

    Class attributes can be overridden before the server starts to inject a
    custom ``Core`` instance or change defaults without subclassing.
    """

    core: Core | None = None  # set to a custom Core instance if needed

    def __init__(self, get_response) -> None:
        self.get_response = get_response
        cfg = {**_DEFAULTS, **getattr(django_settings, "IDEMPY", {})}
        self._core = self.__class__.core or Core()
        self._header_name = cfg["header_name"]
        self._safe_methods = frozenset(cfg["safe_methods"])
        self._replay_content_type = cfg["replay_content_type"]

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method in self._safe_methods:
            return self.get_response(request)

        # Django uppercases header names and prefixes with HTTP_
        django_header = "HTTP_" + self._header_name.upper().replace("-", "_")
        key = request.META.get(django_header)
        if not key:
            return self.get_response(request)

        body = request.body  # reads and caches the body
        idem_req = self._build_idem_request(request, key, body)
        result = self._core.begin(idem_req)

        if result.action == BeginAction.INVALID_REQUEST:
            logger.warning("idempy: invalid request — missing or empty idempotency key")
            return self._json_response({"error": "Missing or empty idempotency key"}, 400)

        if result.action == BeginAction.CONFLICT:
            logger.warning("idempy: conflict on key=%s", key)
            return self._json_response(
                {"error": "Idempotency key conflict: same key, different request fingerprint"},
                409,
            )

        if result.action == BeginAction.REPLAY:
            stored = result.record.idempotency_key
            logger.debug("idempy: replaying key=%s status=%s", key, stored.result_status)
            return HttpResponse(
                content=stored.result_data or b"",
                status=stored.result_status or 200,
                content_type=self._replay_content_type,
            )

        # BeginAction.SUCCESS — new request; run the view and store the result
        record = result.record
        logger.debug("idempy: new request, key=%s", key)

        try:
            response = self.get_response(request)
        except Exception as exc:
            self._core.fail(record, result_error=str(exc))
            logger.warning("idempy: failed key=%s error=%s", key, exc)
            raise

        self._core.complete(
            record,
            result_data=response.content,
            result_status=response.status_code,
        )
        logger.debug("idempy: completed key=%s status=%s", key, response.status_code)
        return response

    def _build_idem_request(
        self,
        request: HttpRequest,
        key: str,
        body: bytes,
    ) -> IdemRequest:
        """Construct an idempy ``Request`` from a Django ``HttpRequest``."""
        fingerprint = hashlib.sha256(
            f"{request.method}:{request.path}:{body.hex()}".encode()
        ).hexdigest()
        return IdemRequest(
            idempotency_key=key,
            fingerprint=fingerprint,
            method=request.method,
            path=request.path,
            url=request.build_absolute_uri(),
            headers={k: v for k, v in request.headers.items()},
            body=body,
            query_params=dict(request.GET),
            path_params=request.resolver_match.kwargs if request.resolver_match else {},
            cookies=request.COOKIES,
            json=_parse_json(body),
        )

    @staticmethod
    def _json_response(body: dict, status: int) -> HttpResponse:
        return HttpResponse(
            content=json.dumps(body),
            status=status,
            content_type="application/json",
        )


def _parse_json(body: bytes) -> dict:
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return {}
