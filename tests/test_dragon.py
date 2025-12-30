from datetime import datetime, timezone

from dragonscales.cache import InMemoryCache
from dragonscales.dragon import Dragon


class FakeModels:
    def __init__(self, models):
        self.models = models
        self.calls = 0

    def list(self):
        self.calls += 1
        return type("Resp", (), {"data": self.models})


class FakeClient:
    def __init__(self, models):
        self.models = FakeModels(models)


def test_refresh_models_respects_ttl(monkeypatch):
    free_model = type("Model", (), {"pricing": {"prompt": 0, "completion": 0}})
    paid_model = type("Model", (), {"pricing": {"prompt": 0.001, "completion": 0}})
    client = FakeClient([free_model, paid_model])
    dragon = Dragon(client, ttl_seconds=3600)

    times = [
        datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 0, 30, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
    ]
    monkeypatch.setattr(dragon, "_now", lambda: times.pop(0))

    first = dragon.refresh_models()
    second = dragon.refresh_models()  # within TTL, should be cached
    third = dragon.refresh_models()  # outside TTL, fetch again

    assert client.models.calls == 2
    assert first is second
    assert third is not second
    assert len(first) == 1
    assert len(third) == 1


def test_refresh_models_reads_from_cache_first(monkeypatch):
    free_model = type("Model", (), {"pricing": {"prompt": 0, "completion": 0}})
    client = FakeClient([free_model])
    cache = InMemoryCache()
    cache.set("dragon:free_models", ["cached"], ttl_seconds=3600)
    dragon = Dragon(client, cache=cache)

    models = dragon.refresh_models()

    assert models == ["cached"]
    assert client.models.calls == 0


def test_refresh_models_writes_to_cache(monkeypatch):
    free_model = type("Model", (), {"pricing": {"prompt": 0, "completion": 0}})
    client = FakeClient([free_model])

    class RecordingCache:
        def __init__(self):
            self.set_calls = []

        def get(self, key):
            return None

        def set(self, key, value, ttl_seconds=None):
            self.set_calls.append((key, value, ttl_seconds))

    cache = RecordingCache()
    dragon = Dragon(client, ttl_seconds=5, cache=cache)

    models = dragon.refresh_models(force=True)

    assert models == [free_model]
    assert cache.set_calls[0] == ("dragon:free_models", [free_model], 5)


def test_is_free_without_pricing_returns_false():
    dragon = Dragon(client=None)

    assert dragon._is_free(object()) is False


def test_is_free_with_mapping_pricing_and_invalid_values():
    dragon = Dragon(client=None)
    model = {"pricing": {"prompt": "abc", "completion": 0}}

    assert dragon._is_free(model) is False


def test_is_free_with_attribute_pricing():
    pricing = type("Pricing", (), {"prompt": 0, "completion": 0})
    model = type("Model", (), {"pricing": pricing})
    dragon = Dragon(client=None)

    assert dragon._is_free(model) is True


def test_now_returns_timezone_aware_datetime():
    dragon = Dragon(client=None)
    now = dragon._now()

    assert now.tzinfo is not None
    assert now.tzinfo.utcoffset(now) is not None
