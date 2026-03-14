from datetime import datetime
from dataclasses import dataclass 

class Status(str, Enum): 
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILED = 'failed'

@dataclass
class IdempotencyKey:
    key: str
    fingerprint: str
    status: str
    created_at: datetime
    updated_at: datetime
    result_data: bytes | None = None
    result_status: int | None = None
    result_error: str | None = None
    