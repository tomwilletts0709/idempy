from typing import Any
from dataclasses import dataclass

@dataclass
class IdempotencyKeySerialiser:
    def __init__(self, key: str, fingerprint: str) -> None:
        self.key = key
        self.fingerprint = fingerprint

    def serialise(self) -> bytes:
        return json.dumps({
            'key': self.key,
            'fingerprint': self.fingerprint
        }).encode('utf-8')