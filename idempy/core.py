from typing import Any
import sys
import os
from datetime import datetime
from idempy.models import IdempotencyKey



DEFAULT_SETTINGS = {
    'idempy_key_prefix': 'idempotency_key_',
    'IdempotencyKey': IdempotencyKey,
    'datetime_class': datetime,
}

class IdempotencyManager: 
    def __init__(self, setttings: dict = DEFAULT_SETTINGS) -> None:
        self.settings = settings
        self.idempotency_key_prefix = settings.get('idempy_key_prefix', 'idempotency_key_')

    def generate_key(self, IdempotencyKey: IdempotencyKey) -> str:
        return f"{self.idempotency_key_prefix}{IdempotencyKey.key}"
