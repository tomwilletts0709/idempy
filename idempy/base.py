from typing import Callable
from abc import ABC, abstractmethod
from idempy.models import IdempotencyKey, Status

class BaseStore(ABC):
    """Abstract base class for idempotency store backends.

    Implement this interface to provide a custom storage backend (e.g. Redis,
    PostgreSQL). All methods must be atomic with respect to concurrent callers.
    """

    @abstractmethod
    def get(self, key: str) -> IdempotencyKey | None:
        """Return the stored record for *key*, or ``None`` if absent or expired."""
        raise NotImplementedError

    @abstractmethod
    def create_in_progress(self, key: str, fingerprint: str) -> bool:
        """Atomically create a PENDING record for *key*.

        Returns ``True`` if the record was created, ``False`` if *key* already
        exists (i.e. a concurrent caller won the race).
        """
        raise NotImplementedError

    @abstractmethod
    def mark_completed(self, key: str, fingerprint: str, result_data: bytes, result_status: int) -> bool:
        """Transition *key* to SUCCESS and store the serialised response.

        Returns ``False`` if *key* is not found or the fingerprint does not match.
        """
        raise NotImplementedError

    @abstractmethod
    def mark_failed(self, key: str, fingerprint: str, result_error: str) -> bool:
        """Transition *key* to FAILED and store the error description.

        Returns ``False`` if *key* is not found or the fingerprint does not match.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove *key* from the store.

        Returns ``True`` if the record existed and was deleted, ``False`` otherwise.
        """
        raise NotImplementedError

    