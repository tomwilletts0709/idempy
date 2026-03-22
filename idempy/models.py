from datetime import datetime
from dataclasses import dataclass 
from enum import Enum

class BeginAction(str, Enum):
    INVALID_REQUEST = 'invalid_request'
    CONFLICT = 'conflict'
    SUCCESS = 'success'

class Status(str, Enum): 
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILED = 'failed'

class State(str, Enum):
    CONFLICT = 'conflict'
    IN_PROGRESS = 'in_progress'
    REPLAY = 'replay'
    PROCESS = 'process'

@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    key: str
    fingerprint: str
    status: str
    created_at: datetime
    updated_at: datetime
    result_data: bytes | None = None
    result_status: int | None = None
    result_error: str | None = None

@dataclass(frozen=True, slots=True)
class Request:
    idempotency_key: str
    fingerprint: str
    method: str
    path: str
    url: str
    headers: dict[str, str]
    body: bytes
    query_params: dict[str, str]
    path_params: dict[str, str]
    cookies: dict[str, str]
    json: dict[str, Any]


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    status: Status
    idempotency_key: IdempotencyKey
    request: Request
    result: Any = None
    error: Exception | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

@dataclass(frozen=True, slots=True)
class BeginResult:
    action: BeginAction
    record: IdempotencyRecord | None = None
    message: str | None = None
  
    

    
