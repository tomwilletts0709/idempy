from typing import Any
import sys 
import os 
import traceback

class IdempotencyError(Exception):
    def __init__(self, idempotency_error: str) -> None:
        self.idempotency_error = idempotency_error
        super().__init__(self.idempotency_error)

class IdempotencyKeyNotFoundError(IdempotencyError):
    pass

class IdempotencyKeyAlreadyExistsError(IdempotencyError):
    pass

class IdempotencyKeyInvalidError(IdempotencyError):
    pass

