import pytest
from idempy.memory import MemoryStore
from idempy.stores import Stores


@pytest.fixture
def stores():
    return Stores(stores={"memory": MemoryStore()}, default="memory")


def test_get_store(stores):
    assert stores.get("memory") is not None


def test_get_store_default(stores):
    assert stores.get() is not None
    assert stores.get("memory") is not None


def test_get_store_not_found(stores):
    with pytest.raises(ValueError, match="Store 'not_found' not found"):
        stores.get("not_found")


def test_get_store_no_default():
    stores = Stores(stores={"memory": MemoryStore()})
    assert stores.get() is not None

def test_create_in_progress():
    stores = Stores(stores={"memory": MemoryStore()})
    assert stores.get("memory").create_in_progress("test", "test") is True
    assert stores.get("memory").create_in_progress("test", "test") is False
    assert stores.get("memory").get("test") is not None

