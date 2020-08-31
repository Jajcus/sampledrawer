
import pytest

from jajcus.sample_drawer import lru_cache


def test_put_get():
    cache = lru_cache.LRUCache()
    cache.put(1, "one")
    cache.put("two", 2)
    cache.put("THREE", "three")
    assert cache.get(1) == "one"
    assert cache.get("two") == 2
    assert cache.get("THREE") == "three"
    assert cache.get(4) is None


def test_put_getitiem():
    cache = lru_cache.LRUCache()
    cache.put(1, "one")
    cache.put("two", 2)
    cache.put("THREE", "three")
    assert cache[1] == "one"
    assert cache["two"] == 2
    assert cache["THREE"] == "three"
    with pytest.raises(KeyError):
        cache[4]


def test_empty():
    cache = lru_cache.LRUCache()
    assert cache.get(1) is None
    with pytest.raises(KeyError):
        cache[2]


def test_overflow():
    cache = lru_cache.LRUCache(maxsize=10)
    for i in range(11):
        cache.put(i, str(i))
    with pytest.raises(KeyError):
        cache[0]
    for i in range(1, 11):
        assert cache[i] == str(i)


def test_lru():
    """check if the least recently used item is kicked out of the cache"""
    cache = lru_cache.LRUCache(maxsize=10)
    for i in range(10):
        cache.put(i, str(i))
    for i in range(0, 10):
        assert cache[i] == str(i)
    assert cache[0] == "0"
    cache.put(10, "10")
    with pytest.raises(KeyError):
        cache[1]
    assert cache[0] == "0"
    for i in range(2, 11):
        assert cache[i] == str(i)
