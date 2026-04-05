import hashlib
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from idempy.memory import MemoryStore
from idempy.models import (
    BeginAction,
    BeginResult,
    IdempotencyKey,
    IdempotencyRecord,
    ReplayAction,
    ReplayResult,
    Request,
    Status,
)
from idempy.stores import Stores

DEFAULT_SETTINGS = {
    'idempy_key_prefix': 'idempotency_key_',
    'datetime_class': datetime,
    'stores': {
        'memory': MemoryStore(),
    },
    'default_store': 'memory',
}


class Core:
    """Orchestrates idempotent operation lifecycle.

    Typical usage::

        core = Core()

        result = core.begin(request)
        if result.action == BeginAction.REPLAY:
            return result.record   # return the cached response
        if result.action == BeginAction.CONFLICT:
            raise ConflictError()

        # perform the work
        response = do_work()

        core.complete(result.record, result_data=response, result_status=200)

    Settings keys:

    - ``idempy_key_prefix`` (str): prefix prepended to every idempotency key.
    - ``datetime_class``: class used to call ``.now()``; override for testing.
    - ``stores`` (dict[str, BaseStore]): named store backends.
    - ``default_store`` (str): name of the store used when none is specified.
    """

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        merged = {**DEFAULT_SETTINGS, **(settings or {})}
        self.settings = merged
        self.stores = Stores(merged['stores'], default=merged.get('default_store'))

    def validate_request(self, request: Request | dict[str, Any]) -> bool:
        """Return ``True`` if *request* contains a non-empty idempotency key.

        Accepts either a ``Request`` dataclass or a plain dict. Falls back to
        the ``Idempotency-Key`` header when the top-level key is absent.
        """
        if request is None:
            return False
        if hasattr(request, 'idempotency_key'):
            key = request.idempotency_key or (request.headers or {}).get('Idempotency-Key')
        else:
            key = request.get('idempotency_key') or (request.get('headers') or {}).get('Idempotency-Key')
        return bool(key and str(key).strip())

    def validate_fingerprint(self, fingerprint: str) -> bool:
        """Return ``True`` if *fingerprint* is a non-empty, non-whitespace string."""
        if not isinstance(fingerprint, str) or not fingerprint:
            return False
        return bool(fingerprint.strip())

    def build_fingerprint(self, request: Request | dict[str, Any]) -> str:
        """Return the SHA-256 hex digest of ``request.fingerprint``.

        The caller is responsible for supplying a stable, canonical fingerprint
        that uniquely identifies the logical request (e.g. a hash of the HTTP
        method, path, and body).
        """
        raw = request.fingerprint if hasattr(request, 'fingerprint') else request.get('fingerprint', '')
        return hashlib.sha256(str(raw).encode()).hexdigest()

    def get_store(self, name: str | None = None) -> "BaseStore":
        from idempy.base import BaseStore
        return self.stores.get(name or self.settings.get('default_store'))

    def build_idempotency_key(self, request: Request) -> str:
        """Return the prefixed store key derived from ``request.idempotency_key``."""
        prefix = self.settings.get('idempy_key_prefix', 'idempotency_key_')
        return f"{prefix}{request.idempotency_key}"

    def _to_request(self, request: Request | dict[str, Any]) -> Request:
        """Coerce *request* to a ``Request`` dataclass, applying sensible HTTP defaults."""
        if isinstance(request, Request):
            return request
        defaults = {
            "method": "",
            "path": "",
            "url": "",
            "headers": request.get("headers", {}),
            "body": request.get("body", b""),
            "query_params": request.get("query_params", {}),
            "path_params": request.get("path_params", {}),
            "cookies": request.get("cookies", {}),
            "json": request.get("json", {}),
        }
        return Request(
            idempotency_key=str(request.get("idempotency_key", "")),
            fingerprint=str(request.get("fingerprint", "")),
            **defaults,
        )

    def begin(self, request: Request | dict[str, Any]) -> BeginResult:
        """Start an idempotent operation, or surface a prior outcome.

        Possible ``BeginResult.action`` values:

        - ``BeginAction.SUCCESS`` — new request; a PENDING record has been created.
          Proceed with the work, then call :meth:`complete` or :meth:`fail`.
        - ``BeginAction.REPLAY`` — identical request seen before; the stored record
          is attached. Return the cached response without re-executing.
        - ``BeginAction.CONFLICT`` — same key, different fingerprint; the caller
          must surface this as an error (e.g. HTTP 409).
        - ``BeginAction.INVALID_REQUEST`` — missing or empty idempotency key.
        """
        req = self._to_request(request) if isinstance(request, dict) else request
        if not self.validate_request(req):
            logger.warning("begin: invalid request — missing or empty idempotency key")
            return BeginResult(action=BeginAction.INVALID_REQUEST, message='Invalid request')

        idempotency_key = self.build_idempotency_key(req)
        fingerprint = self.build_fingerprint(req)
        store = self.get_store(getattr(req, 'store', None))

        existing = store.get(idempotency_key)
        if existing is not None:
            if existing.fingerprint == fingerprint:
                logger.debug("begin: replay key=%s", idempotency_key)
                return BeginResult(
                    action=BeginAction.REPLAY,
                    record=self._key_to_record(existing, req),
                    message='Replay',
                )
            logger.warning("begin: conflict key=%s", idempotency_key)
            return BeginResult(action=BeginAction.CONFLICT, message='Conflict')

        store.create_in_progress(idempotency_key, fingerprint)
        logger.debug("begin: new key=%s", idempotency_key)
        now = datetime.now()
        key_obj = IdempotencyKey(
            key=idempotency_key,
            fingerprint=fingerprint,
            status=Status.PENDING,
            created_at=now,
            updated_at=now,
        )
        record = IdempotencyRecord(
            status=Status.PENDING,
            idempotency_key=key_obj,
            request=req,
        )
        return BeginResult(action=BeginAction.SUCCESS, record=record, message='Success')

    def _key_to_record(self, key: IdempotencyKey, request: Request) -> IdempotencyRecord:
        """Convert a raw ``IdempotencyKey`` from the store into an ``IdempotencyRecord``."""
        return IdempotencyRecord(
            status=Status(key.status) if key.status in Status.__members__ else Status.PENDING,
            idempotency_key=key,
            request=request,
        )

    def complete(
        self,
        record: IdempotencyRecord,
        result_data: bytes,
        result_status: int,
    ) -> Status:
        """Mark *record* as successfully completed and persist the response.

        Call this after the operation finishes without error. Updates the record
        in-place and returns ``Status.SUCCESS``.
        """
        store = self.get_store(getattr(record.request, 'store', None))
        store.mark_completed(
            record.idempotency_key.key,
            record.idempotency_key.fingerprint,
            result_data,
            result_status,
        )
        record.status = Status.SUCCESS
        record.result = result_data
        record.updated_at = datetime.now()
        logger.info("complete: key=%s status=%s", record.idempotency_key.key, result_status)
        return Status.SUCCESS

    def fail(self, record: IdempotencyRecord, result_error: str) -> Status:
        """Mark *record* as failed and persist the error description.

        Call this when the operation raises an unrecoverable error. Updates the
        record in-place and returns ``Status.FAILED``.
        """
        store = self.get_store(getattr(record.request, 'store', None))
        store.mark_failed(
            record.idempotency_key.key,
            record.idempotency_key.fingerprint,
            result_error,
        )
        record.status = Status.FAILED
        record.error = RuntimeError(result_error)
        record.updated_at = datetime.now()
        logger.warning("fail: key=%s error=%r", record.idempotency_key.key, result_error)
        return Status.FAILED

    def replay(self, request: Request) -> ReplayResult:
        """Retrieve the stored result for a previously completed request.

        Possible ``ReplayResult.action`` values:

        - ``ReplayAction.SUCCESS`` — record found; ``result.record`` contains
          the stored response.
        - ``ReplayAction.NOT_FOUND`` — no record exists for this key.
        - ``ReplayAction.CONFLICT`` — key exists but fingerprint differs.
        - ``ReplayAction.INVALID_REQUEST`` — missing or empty idempotency key.
        """
        if not self.validate_request(request):
            return ReplayResult(
                action=ReplayAction.INVALID_REQUEST,
                message="Invalid request",
            )
        idempotency_key = self.build_idempotency_key(request)
        fingerprint = self.build_fingerprint(request)
        store = self.get_store(getattr(request, 'store', None))
        record = store.get(idempotency_key)
        if record is None:
            return ReplayResult(
                action=ReplayAction.NOT_FOUND,
                message="Replay not found",
            )
        if record.fingerprint != fingerprint:
            return ReplayResult(
                action=ReplayAction.CONFLICT,
                message="Fingerprint conflict",
            )
        return ReplayResult(
            action=ReplayAction.SUCCESS,
            record=self._key_to_record(record, request),
            message="Replay found",
        )

    def get_status(self, request: Request) -> Status:
        """Return the current ``Status`` for *request*.

        Returns ``Status.NOT_FOUND`` when no record exists for the key.
        """
        idempotency_key = self.build_idempotency_key(request)
        store = self.get_store(getattr(request, 'store', None))
        record = store.get(idempotency_key)
        if record is None:
            return Status.NOT_FOUND
        status_val = getattr(record.status, "value", record.status)
        try:
            return Status(status_val)
        except ValueError:
            return Status.PENDING
