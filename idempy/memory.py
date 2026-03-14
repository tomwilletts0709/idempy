import time
from typing import Dict, Any, Optional, Callable
from idempy.base import BaseStore
from idempy.models import IdempotencyKey, Status

class MemoryStore(BaseStore):
    """ in memory store for idempotency keys """

    expiry_seconds: int = 60 * 60 * 24 * 30 # 30 days
    

    def __init__(self, clear: bool = False) -> None: 
        self.store: Dict[str, IdempotencyKey] = {}
        self.lock = Lock()
        if clear:
            self.clear_idempotency_keys()

    def get(self, key: str) -> Optional[IdempotencyKey]:
        record = self.store.get(key)
        if record is None: 
            return None
        
        if self.is_expired(record):
            self.delete_idempotency_key(key)
            return None
        
        return record

    def store_response_data(self, key: str, result_data: bytes, result_status: int) -> None:
        self.response_store[key] = {
            'result_data': result_data,
            'result_status': result_status,
        }

    def get_stored_response(self, key: str) -> Optional[bytes]:
        if key not in self.store:
            return None
        return self.store[key].result_data

    def store_idempotency_key(self, key: str, idempotency_key: IdempotencyKey) -> None:
        self.store[key] = idempotency_key
    
    def delete_idempotency_key(self, key: str) -> None:
        if key in self.store:
            del self.store[key]

    def clear_idempotency_keys(self) -> None:
        self.store.clear()
