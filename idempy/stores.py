from typing import TYPE_CHECKING

from idempy.base import BaseStore


class Stores:
    """Registry that maps named store backends and resolves a default.

    Pass an instance to ``Core`` via the ``stores`` settings key to control
    which backends are available and which is used when none is specified.

    Example::

        stores = Stores({"memory": MemoryStore(), "redis": RedisStore(...)}, default="redis")
        core = Core(settings={"stores": stores._stores, "default_store": "redis"})
    """

    def __init__(self, stores: dict[str, BaseStore], default: str | None = None) -> None:
        self._stores = stores
        self._default = default or ("memory" if "memory" in stores else next(iter(stores), None))

    def get(self, name: str | None = None) -> BaseStore:
        """Return the named store, or the default store when *name* is ``None``.

        Raises ``ValueError`` if the requested store does not exist.
        """
        key = name or self._default
        if key is None:
            raise ValueError("No store configured and no default available")
        store = self._stores.get(key)
        if store is None:
            raise ValueError(
                f"Store '{key}' not found. Available: {list(self._stores)}"
            )
        return store

