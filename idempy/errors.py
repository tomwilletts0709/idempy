from typing import Any
import sys 
import os 
import traceback

class IdempotencyError(Exception):
    """Base exception for all idempy errors.

    The human-readable reason is available on the ``idempotency_error`` attribute
    and is also passed to the standard ``Exception`` message.
    """

    def __init__(self, idempotency_error: str) -> None:
        self.idempotency_error = idempotency_error
        super().__init__(self.idempotency_error)

class IdempotencyKeyNotFoundError(IdempotencyError):
    """Raised when an operation references a key that does not exist in the store."""

class IdempotencyKeyAlreadyExistsError(IdempotencyError):
    """Raised when attempting to create a key that is already present in the store."""

class IdempotencyKeyInvalidError(IdempotencyError):
    """Raised when the supplied idempotency key fails validation (e.g. empty string)."""

