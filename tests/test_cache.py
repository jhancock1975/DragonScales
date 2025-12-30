import sys
from types import SimpleNamespace

from dragonscales.cache import InMemoryCache, RedisCache, redis_cache_from_url


def test_in_memory_cache_respects_ttl_zero_expires_immediately():
    cache = InMemoryCache()
    cache.set("key", "value", ttl_seconds=0)
    cache.set("key-persist", "value", ttl_seconds=None)

    assert cache.get("key") is None
    assert cache.get("key-persist") == "value"
    assert cache.get("missing") is None


class DummyRedis:
    def __init__(self):
        self.store = {}
        self.setex_calls = []

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.setex_calls.append((key, ttl, value))
        self.store[key] = value

    def set(self, key, value):
        self.store[key] = value


def test_redis_cache_set_and_get_round_trips_pickled_object():
    client = DummyRedis()
    cache = RedisCache(client)
    payload = {"a": 1}

    assert cache.get("missing") is None
    cache.set("key", payload, ttl_seconds=10)
    assert cache.get("key") == payload
    assert client.setex_calls[0][1] == 10


def test_redis_cache_handles_non_pickled_values():
    client = DummyRedis()
    cache = RedisCache(client)
    client.store["bad"] = b"not-a-json"

    assert cache.get("bad") is None
    cache.set("plain", "value", ttl_seconds=None)
    assert client.store["plain"] is not None


def test_redis_cache_from_url_uses_redis_module(monkeypatch):
    dummy_client = DummyRedis()

    class RedisFactory:
        @staticmethod
        def from_url(url):
            RedisFactory.last_url = url
            return dummy_client

    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=RedisFactory))

    cache = redis_cache_from_url("redis://cache:6379/0")

    assert isinstance(cache, RedisCache)
    assert getattr(RedisFactory, "last_url") == "redis://cache:6379/0"
