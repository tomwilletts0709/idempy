from typing import Any

class IdempotencyError(Exception):
    pass

class IdempotencyKeyNotFoundError(IdempotencyError):
    pass

class IdempotencyKeyAlreadyExistsError(IdempotencyError):
    pass

class IdempotencyKeyInvalidError(IdempotencyError):
    pass

