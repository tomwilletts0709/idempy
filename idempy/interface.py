from typing import Any, Protocol
from dataclasses import dataclass
from datetime import datetime
from idempy.models import IdempotencyKey



class IdempotencyProtocol(Protocol):
    def __init__(self, key: str, fingerprint: str) -> None:
        self.key = key
        self.fingerprint = fingerprint

    def get_key(self) -> str:
        pass


    