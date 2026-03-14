from typing import Callable
from abc import ABC, abstractmethod
from idempy.models import IdempotencyKey, Status

class BaseStore(ABC): 
    @abstractmethod
    def get(self, key: str) -> IdempotencyKey | None:
        raise NotImplementedError

    @abstractmethod
    def create_in_progress(self, key: str, fingerprint: str) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def mark_completed(self, key: str, fingerprint: str, result_data: bytes, result_status: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mark_failed(self, key: str, fingerprint: str, result_error: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mark_pending(self, key: str, fingerprint: str) -> bool:
        raise NotImplementedError