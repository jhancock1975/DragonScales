import runpy

from dragonscales.__main__ import build_dragon, main
from dragonscales.config import Settings
import runpy


def test_main_instantiates_client_from_env(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    dragon = main()

    assert capsys.readouterr().out == "dragonscales\n"
    assert dragon.client.api_key == "test-key"
    assert str(dragon.client.base_url).rstrip("/") == "https://openrouter.ai/api/v1"


def test_module_entrypoint_executes(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "module-key")

    runpy.run_module("dragonscales.__main__", run_name="__main__")

    assert "dragonscales" in capsys.readouterr().out


def test_build_dragon_uses_cache_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class FakeCache:
        def __init__(self, url):
            self.url = url

    monkeypatch.setenv("CACHE_URL", "redis://cache:6379/0")
    monkeypatch.setattr("dragonscales.__main__.redis_cache_from_url", lambda url: FakeCache(url))

    dragon = build_dragon()

    assert isinstance(dragon.cache, FakeCache)
    assert dragon.cache.url == "redis://cache:6379/0"


def test_build_dragon_reads_from_vault_when_configured(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class FakeCache:
        def __init__(self, url):
            self.url = url

    def fake_settings(**kwargs):
        return Settings(openrouter_api_key="vault-key", cache_url="redis://vault:6379/0")

    monkeypatch.setattr("dragonscales.__main__.load_settings", fake_settings)
    monkeypatch.setattr("dragonscales.__main__.redis_cache_from_url", lambda url: FakeCache(url))

    dragon = build_dragon()

    assert dragon.client.api_key == "vault-key"
    assert isinstance(dragon.cache, FakeCache)
    assert dragon.cache.url == "redis://vault:6379/0"
