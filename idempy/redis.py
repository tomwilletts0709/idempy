"""Redis-backed idempotency store.

Requires the ``redis`` package::

    pip install redis

Usage::

    from redis import Redis
    from idempy import Core
    from idempy.redis import RedisStore

    store = RedisStore(Redis(host="localhost", port=6379, db=0))
    core = Core(settings={"stores": {"redis": store}, "default_store": "redis"})

``RedisStore`` serialises each ``IdempotencyKey`` to a Redis hash and uses
``SET NX`` (set-if-not-exists) for atomic creation, so it is safe under
horizontal scale with multiple concurrent workers.

TTL is enforced by Redis natively via ``EXPIRE`` — no background job needed.
Default TTL is 30 days, matching ``MemoryStore``.
"""

import logging
from datetime import datetime
from typing import Optional

from redis import Redis
from redis.exceptions import RedisError

from idempy.base import BaseStore
from idempy.models import IdempotencyKey, Status

logger = logging.getLogger(__name__)

_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

# Hash field names stored in Redis
_F_FINGERPRINT    = "fingerprint"
_F_STATUS         = "status"
_F_CREATED_AT     = "created_at"
_F_UPDATED_AT     = "updated_at"
_F_RESULT_DATA    = "result_data"
_F_RESULT_STATUS  = "result_status"
_F_RESULT_ERROR   = "result_error"

# Sentinel stored in Redis when an optional bytes field is absent
_NONE = b""


class RedisStore(BaseStore):
    """Durable, distributed idempotency store backed by Redis.

    Each idempotency key is stored as a Redis hash with a TTL.  Atomic creation
    uses ``SET NX`` on a lock key so that only one caller can claim a key — all
    others receive ``False`` from :meth:`create_in_progress` and must treat the
    request as a replay or conflict.

    Args:
        client: A connected ``redis.Redis`` instance.
        ttl_seconds: Time-to-live for every key. Defaults to 30 days.
        key_prefix: Optional namespace prefix applied to all Redis keys, useful
            when multiple applications share a Redis instance.
    """

    def __init__(
        self,
        client: Redis,
        ttl_seconds: int = _TTL_SECONDS,
        key_prefix: str = "",
    ) -> None:
        self._redis = client
        self._ttl = ttl_seconds
        self._prefix = key_prefix

    # ------------------------------------------------------------------
    # BaseStore interface
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[IdempotencyKey]:
        """Return the stored record for *key*, or ``None`` if absent."""
        rkey = self._rkey(key)
        try:
            data = self._redis.hgetall(rkey)
        except RedisError:
            logger.exception("idempy RedisStore.get failed for key=%s", key)
            return None

        if not data:
            return None

        return self._deserialise(key, data)

    def create_in_progress(self, key: str, fingerprint: str) -> bool:
        """Atomically create a PENDING record using SET NX.

        Returns ``True`` if this caller won the race, ``False`` if the key
        already exists (another caller or a prior request got there first).
        """
        lock_key = self._rkey(key) + ":lock"
        try:
            acquired = self._redis.set(lock_key, b"1", nx=True, ex=self._ttl)
        except RedisError:
            logger.exception("idempy RedisStore.create_in_progress failed for key=%s", key)
            return False

        if not acquired:
            return False

        now = datetime.now()
        rkey = self._rkey(key)
        mapping = self._serialise(
            fingerprint=fingerprint,
            status=Status.PENDING,
            created_at=now,
            updated_at=now,
        )
        try:
            pipe = self._redis.pipeline()
            pipe.hset(rkey, mapping=mapping)
            pipe.expire(rkey, self._ttl)
            pipe.execute()
        except RedisError:
            logger.exception("idempy RedisStore.create_in_progress hset failed for key=%s", key)
            return False

        return True

    def mark_completed(
        self,
        key: str,
        fingerprint: str,
        result_data: bytes,
        result_status: int,
    ) -> bool:
        """Transition *key* to SUCCESS and store the response."""
        return self._update(
            key=key,
            fingerprint=fingerprint,
            status=Status.SUCCESS,
            extra={
                _F_RESULT_DATA: result_data if result_data is not None else _NONE,
                _F_RESULT_STATUS: str(result_status),
            },
        )

    def mark_failed(self, key: str, fingerprint: str, result_error: str) -> bool:
        """Transition *key* to FAILED and store the error description."""
        return self._update(
            key=key,
            fingerprint=fingerprint,
            status=Status.FAILED,
            extra={_F_RESULT_ERROR: result_error},
        )

    def delete(self, key: str) -> bool:
        """Remove *key* and its lock from Redis. Returns ``True`` if it existed."""
        rkey = self._rkey(key)
        lock_key = rkey + ":lock"
        try:
            deleted = self._redis.delete(rkey, lock_key)
        except RedisError:
            logger.exception("idempy RedisStore.delete failed for key=%s", key)
            return False
        return deleted > 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rkey(self, key: str) -> str:
        """Return the Redis key, with optional namespace prefix."""
        return f"{self._prefix}{key}" if self._prefix else key

    def _update(
        self,
        key: str,
        fingerprint: str,
        status: Status,
        extra: dict,
    ) -> bool:
        """Verify fingerprint then atomically update status + extra fields."""
        rkey = self._rkey(key)
        try:
            stored_fp = self._redis.hget(rkey, _F_FINGERPRINT)
        except RedisError:
            logger.exception("idempy RedisStore._update hget failed for key=%s", key)
            return False

        if stored_fp is None:
            return False
        if stored_fp.decode() != fingerprint:
            return False

        now = datetime.now()
        mapping: dict = {
            _F_STATUS: status.value,
            _F_UPDATED_AT: now.isoformat(),
            **extra,
        }
        try:
            pipe = self._redis.pipeline()
            pipe.hset(rkey, mapping=mapping)
            pipe.expire(rkey, self._ttl)
            pipe.execute()
        except RedisError:
            logger.exception("idempy RedisStore._update hset failed for key=%s", key)
            return False

        return True

    @staticmethod
    def _serialise(
        fingerprint: str,
        status: Status,
        created_at: datetime,
        updated_at: datetime,
    ) -> dict:
        return {
            _F_FINGERPRINT: fingerprint,
            _F_STATUS: status.value,
            _F_CREATED_AT: created_at.isoformat(),
            _F_UPDATED_AT: updated_at.isoformat(),
        }

    @staticmethod
    def _deserialise(key: str, data: dict) -> IdempotencyKey:
        def _str(field: bytes) -> str:
            return data[field].decode() if field in data else ""

        def _dt(field: bytes) -> datetime:
            raw = data.get(field, b"")
            try:
                return datetime.fromisoformat(raw.decode())
            except (ValueError, AttributeError):
                return datetime.now()

        def _bytes(field: bytes) -> bytes | None:
            raw = data.get(field)
            if raw is None or raw == _NONE:
                return None
            return raw

        def _int(field: bytes) -> int | None:
            raw = data.get(field)
            if raw is None:
                return None
            try:
                return int(raw.decode())
            except (ValueError, AttributeError):
                return None

        return IdempotencyKey(
            key=key,
            fingerprint=_str(_F_FINGERPRINT.encode()),
            status=_str(_F_STATUS.encode()),
            created_at=_dt(_F_CREATED_AT.encode()),
            updated_at=_dt(_F_UPDATED_AT.encode()),
            result_data=_bytes(_F_RESULT_DATA.encode()),
            result_status=_int(_F_RESULT_STATUS.encode()),
            result_error=_str(_F_RESULT_ERROR.encode()) or None,
        )
