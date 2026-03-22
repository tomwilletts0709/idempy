from typing import Any
import sys
import os
from datetime import datetime
from idempy.models import IdempotencyKey, Request, Process, Replay, InProgress, Conflict
from idempy.memory import MemoryStore
import hashlib
from idempy.errors import IdempotencyKeyNotFoundError, IdempotencyKeyAlreadyExistsError, IdempotencyKeyInvalidError
from idempy.validator import ValidatedField, non_empty, min_value



DEFAULT_SETTINGS = {
    'idempy_key_prefix': 'idempotency_key_',
    'IdempotencyKey': IdempotencyKey,
    'datetime_class': datetime,
    'stores': {
        'memory': MemoryStore(),
    },
}


class Core:
    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        self.settings = DEFAULT_SETTINGS
        self.stores = Stores(settings['stores'])
           
    def validate_request(self, request: dict[str, Any]) -> bool:
        if request is None:
            return False
        
        if request.headers.get('Idempotency-Key') is None:
            return False
        
        return True
    
    def validate_fingerprint(self, fingerprint: str) -> bool:
        if not isinstance(fingerprint, str) or not fingerprint: 
            return False
        
        if not fingerprint.strip(): 
            return False 
        
        return True

    def build_fingerprint(self, request: dict[str, Any]) -> str:
        return hashlib.sha256(request['fingerprint'].encode()).hexdigest()
        
        if not request['fingerprint'].strip(): 
            return False 
        
        return request['fingerprint']

    def get_store(self, memory: MemoryStore) -> MemoryStore:
        return memory

    def begin(self, request: Request) -> None:
        if not self.validate_request(request):
            return BeginResult(action=BeginAction.INVALID_REQUEST, message='Invalid request')

        idempotency_key = self.build_idempotency_key(request)
        fingerprint = self.build_fingerprint(request)
        store = self.get_store(request.store)

        if store.get(idempotency_key) is not None:
            return BeginResult(action=BeginAction.CONFLICT, message='Conflict')

        store.create_in_progress(idempotency_key, fingerprint)
        return BeginResult(action=BeginAction.SUCCESS, message='Success')

    



    def complete(self, request: Request) -> None:
        pass 

    def fail(self, request: Request) -> None:
        pass 

    def replay(self, request: Request) -> None:
        pass

    def get_status(self, request: Request) -> Status:
        pass

        
        


        

        


