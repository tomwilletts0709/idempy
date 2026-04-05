"""Flask extension that adds per-request idempotency via before/after hooks.

Usage — application factory::

    from idempy.flask_middleware import IdemMiddleware

    middleware = IdemMiddleware()

    def create_app():
        app = Flask(__name__)
        middleware.init_app(app)
        return app

Usage — direct init::

    app = Flask(__name__)
    IdemMiddleware(app)

Any request that carries an ``Idempotency-Key`` header (configurable) will be
gated through ``Core.begin()``.  Safe methods (GET, HEAD, OPTIONS) are skipped
entirely.  The outcome drives what happens next:

- **New request** — a PENDING record is created; the view runs normally;
  ``complete()`` or ``fail()`` is called automatically on the way out.
- **Replay** — the view is never called; the stored response is returned as-is.
- **Conflict** — the view is never called; a 409 is returned immediately.
- **No header** — the request passes through untouched.
"""

import hashlib
import json
import logging
from typing import Container

from flask import Flask, Response, g
from flask import request as flask_request

from idempy.core import Core
from idempy.models import BeginAction, Request

logger = logging.getLogger(__name__)


class IdemMiddleware:
    """Flask extension for automatic request idempotency.

    Args:
        app: Flask application. Pass here for direct init, or call
            :meth:`init_app` later for the application-factory pattern.
        core: ``Core`` instance to use. Defaults to ``Core()`` with the
            built-in ``MemoryStore``.
        header_name: HTTP header the client uses to supply the idempotency
            key. Defaults to ``"Idempotency-Key"``.
        safe_methods: HTTP methods that are never gated. Defaults to
            ``("GET", "HEAD", "OPTIONS")``.
        replay_content_type: ``Content-Type`` used when returning a replayed
            response. Defaults to ``"application/json"``.
    """

    def __init__(
        self,
        app: Flask | None = None,
        core: Core | None = None,
        header_name: str = "Idempotency-Key",
        safe_methods: Container[str] = ("GET", "HEAD", "OPTIONS"),
        replay_content_type: str = "application/json",
    ) -> None:
        self.core = core or Core()
        self.header_name = header_name
        self.safe_methods = frozenset(safe_methods)
        self.replay_content_type = replay_content_type

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Register before/after hooks on *app*."""
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def _before_request(self) -> Response | None:
        if flask_request.method in self.safe_methods:
            return None

        key = flask_request.headers.get(self.header_name)
        if not key:
            return None  # no header — pass through

        req = self._build_idem_request(key)
        result = self.core.begin(req)

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
            return Response(
                stored.result_data or b"",
                status=stored.result_status or 200,
                content_type=self.replay_content_type,
            )

        # BeginAction.SUCCESS — new request; stash record for after_request
        g._idempy_record = result.record
        logger.debug("idempy: new request, key=%s", key)
        return None

    def _after_request(self, response: Response) -> Response:
        """Called after the view returns successfully. Marks the record complete."""
        record = getattr(g, "_idempy_record", None)
        if record is None:
            return response
        self.core.complete(
            record,
            result_data=response.get_data(),
            result_status=response.status_code,
        )
        logger.debug("idempy: completed key=%s", record.idempotency_key.key)
        return response

    def _teardown_request(self, exc: BaseException | None) -> None:
        """Called after every request. Marks the record failed if an exception occurred."""
        if exc is None:
            return
        record = getattr(g, "_idempy_record", None)
        if record is None:
            return
        self.core.fail(record, result_error=str(exc))
        logger.warning(
            "idempy: failed key=%s error=%s",
            record.idempotency_key.key,
            exc,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_idem_request(self, key: str) -> Request:
        """Construct an idempy ``Request`` from the current Flask request context."""
        body = flask_request.get_data()
        fingerprint = hashlib.sha256(
            f"{flask_request.method}:{flask_request.path}:{body.hex()}".encode()
        ).hexdigest()
        return Request(
            idempotency_key=key,
            fingerprint=fingerprint,
            method=flask_request.method,
            path=flask_request.path,
            url=flask_request.url,
            headers=dict(flask_request.headers),
            body=body,
            query_params=dict(flask_request.args),
            path_params=flask_request.view_args or {},
            cookies=dict(flask_request.cookies),
            json=flask_request.get_json(silent=True) or {},
        )

    @staticmethod
    def _json_response(body: dict, status: int) -> Response:
        return Response(json.dumps(body), status=status, content_type="application/json")
