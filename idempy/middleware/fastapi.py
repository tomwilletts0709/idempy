"""FastAPI middleware for automatic request idempotency.

Usage::

    from fastapi import FastAPI
    from idempy.middleware.fastapi import IdemMiddleware

    app = FastAPI()
    app.add_middleware(IdemMiddleware)

With options::

    app.add_middleware(
        IdemMiddleware,
        core=Core(settings={...}),
        header_name="X-Request-Id",
    )

Any request that carries an ``Idempotency-Key`` header (configurable) is gated
through ``Core.begin()``.  Safe methods (GET, HEAD, OPTIONS) are skipped.

- **New request** — PENDING record created; endpoint runs; result stored.
- **Replay** — endpoint never called; stored response returned as-is.
- **Conflict** — endpoint never called; 409 returned immediately.
- **No header** — request passes through untouched.
"""

import hashlib
import json
import logging
from typing import Container

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from idempy.core import Core
from idempy.models import BeginAction
from idempy.models import Request as IdemRequest

logger = logging.getLogger(__name__)


class IdemMiddleware(BaseHTTPMiddleware):
    """Starlette/FastAPI middleware for automatic request idempotency.

    Args:
        app: The ASGI application to wrap (injected by FastAPI automatically).
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
        app: ASGIApp,
        core: Core | None = None,
        header_name: str = "Idempotency-Key",
        safe_methods: Container[str] = ("GET", "HEAD", "OPTIONS"),
        replay_content_type: str = "application/json",
    ) -> None:
        super().__init__(app)
        self.core = core or Core()
        self.header_name = header_name
        self.safe_methods = frozenset(safe_methods)
        self.replay_content_type = replay_content_type

    async def dispatch(self, request: StarletteRequest, call_next) -> Response:
        if request.method in self.safe_methods:
            return await call_next(request)

        key = request.headers.get(self.header_name)
        if not key:
            return await call_next(request)

        body = await request.body()
        idem_req = self._build_idem_request(request, key, body)
        result = self.core.begin(idem_req)

        if result.action == BeginAction.INVALID_REQUEST:
            logger.warning("idempy: invalid request — missing or empty idempotency key")
            return JSONResponse({"error": "Missing or empty idempotency key"}, status_code=400)

        if result.action == BeginAction.CONFLICT:
            logger.warning("idempy: conflict on key=%s", key)
            return JSONResponse(
                {"error": "Idempotency key conflict: same key, different request fingerprint"},
                status_code=409,
            )

        if result.action == BeginAction.REPLAY:
            stored = result.record.idempotency_key
            logger.debug("idempy: replaying key=%s status=%s", key, stored.result_status)
            return Response(
                content=stored.result_data or b"",
                status_code=stored.result_status or 200,
                media_type=self.replay_content_type,
            )

        # BeginAction.SUCCESS — new request; call the endpoint and store the result
        record = result.record
        logger.debug("idempy: new request, key=%s", key)

        try:
            response = await call_next(request)
        except Exception as exc:
            self.core.fail(record, result_error=str(exc))
            logger.warning("idempy: failed key=%s error=%s", key, exc)
            raise

        response_body = b"".join([chunk async for chunk in response.body_iterator])
        self.core.complete(record, result_data=response_body, result_status=response.status_code)
        logger.debug("idempy: completed key=%s status=%s", key, response.status_code)

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    def _build_idem_request(
        self,
        request: StarletteRequest,
        key: str,
        body: bytes,
    ) -> IdemRequest:
        """Construct an idempy ``Request`` from the current Starlette request."""
        fingerprint = hashlib.sha256(
            f"{request.method}:{request.url.path}:{body.hex()}".encode()
        ).hexdigest()
        return IdemRequest(
            idempotency_key=key,
            fingerprint=fingerprint,
            method=request.method,
            path=request.url.path,
            url=str(request.url),
            headers=dict(request.headers),
            body=body,
            query_params=dict(request.query_params),
            path_params=dict(request.path_params),
            cookies=dict(request.cookies),
            json=_parse_json(body),
        )


def _parse_json(body: bytes) -> dict:
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return {}
