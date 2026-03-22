from typing TYPE_CHECKING, Any

if TYPE_CHECKING:
    from idempy.core import Core

class Stores: 
    def __init__(self, stores: dict[str, BaseStore], default: str | None = None) -> None:
        self.stores = stores 
        self.default = default

    def get(self, name: str) -> BaseStore:
    key = name or self.default
    if key is None: 
        raise ValueError("No default store configured")
    store = self.stores.get(key)
    if store is None:
        raise ValueError(f"Store {key} not found")
    return store

