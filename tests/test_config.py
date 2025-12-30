import sys
from types import SimpleNamespace

import pytest

from dragonscales.config import Settings, build_cache_url, load_settings, load_vault_secrets


def test_build_cache_url_from_parts():
    source = {
        "REDIS_USERNAME": "cache-user",
        "REDIS_PASSWORD": "secretpw",
        "REDIS_HOST": "redis.internal",
        "REDIS_PORT": "6380",
        "REDIS_DB": "2",
    }

    assert build_cache_url(source) == "redis://cache-user:secretpw@redis.internal:6380/2"


def test_build_cache_url_requires_password():
    assert build_cache_url({}) is None


def test_build_cache_url_prefers_full_url():
    assert build_cache_url({"CACHE_URL": "redis://cached"}) == "redis://cached"


def test_load_settings_prefers_env_over_vault(monkeypatch):
    def fake_vault_loader(env):
        return {"OPENROUTER_API_KEY": "vault-key", "CACHE_URL": "redis://vault:6379/0"}

    settings = load_settings(
        env={"OPENROUTER_API_KEY": "env-key"},
        vault_loader=fake_vault_loader,
    )

    assert isinstance(settings, Settings)
    assert settings.openrouter_api_key == "env-key"
    assert settings.cache_url == "redis://vault:6379/0"


def test_load_settings_allows_overrides(monkeypatch):
    settings = load_settings(
        api_key="override-key",
        cache_url="redis://override",
        env={"OPENROUTER_API_KEY": "env-key"},
        vault_loader=lambda env: {},
    )

    assert settings.openrouter_api_key == "override-key"
    assert settings.cache_url == "redis://override"


def test_load_settings_raises_without_api_key():
    with pytest.raises(ValueError):
        load_settings(env={}, vault_loader=lambda env: {})


def test_load_vault_secrets_reads_from_kv(monkeypatch):
    class DummyKV:
        def __init__(self):
            self.read_calls = []

        def read_secret_version(self, path, mount_point):
            self.read_calls.append((path, mount_point))
            return {"data": {"data": {"OPENROUTER_API_KEY": "vault-key", "CACHE_URL": "redis://vault:6379/0"}}}

    dummy_kv = DummyKV()

    class DummyClient:
        def __init__(self, url):
            self.url = url
            self.token = None
            self.auth = SimpleNamespace(approle=SimpleNamespace(login=lambda role_id, secret_id: None))
            self.secrets = SimpleNamespace(kv=SimpleNamespace(v2=dummy_kv))

    monkeypatch.setitem(sys.modules, "hvac", SimpleNamespace(Client=DummyClient))

    secrets = load_vault_secrets(
        {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_TOKEN": "token",
            "VAULT_SECRET_PATH": "dragonscales",
            "VAULT_KV_MOUNT": "secret",
        }
    )

    assert secrets["OPENROUTER_API_KEY"] == "vault-key"
    assert dummy_kv.read_calls == [("dragonscales", "secret")]


def test_load_vault_secrets_requires_hvac(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "hvac":
            raise ImportError("no hvac")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError):
        load_vault_secrets({"VAULT_ADDR": "http://vault"})


def test_load_vault_secrets_requires_auth(monkeypatch):
    class DummyClient:
        def __init__(self, url):
            self.url = url
            self.token = None
            self.auth = SimpleNamespace(approle=SimpleNamespace(login=lambda role_id, secret_id: None))
            self.secrets = SimpleNamespace(kv=SimpleNamespace(v2=SimpleNamespace(read_secret_version=lambda *a, **k: {})))

    monkeypatch.setitem(sys.modules, "hvac", SimpleNamespace(Client=DummyClient))

    with pytest.raises(RuntimeError):
        load_vault_secrets({"VAULT_ADDR": "http://vault"})


def test_load_vault_secrets_supports_approle(monkeypatch):
    class DummyKV:
        def __init__(self):
            self.read_calls = []

        def read_secret_version(self, path, mount_point):
            self.read_calls.append((path, mount_point))
            return {"data": {"data": {"OPENROUTER_API_KEY": "role-key"}}}

    dummy_kv = DummyKV()

    class DummyAppRole:
        def __init__(self):
            self.login_calls = []

        def login(self, role_id, secret_id):
            self.login_calls.append((role_id, secret_id))

    dummy_approle = DummyAppRole()

    class DummyClient:
        def __init__(self, url):
            self.url = url
            self.token = None
            self.auth = SimpleNamespace(approle=dummy_approle)
            self.secrets = SimpleNamespace(kv=SimpleNamespace(v2=dummy_kv))

    monkeypatch.setitem(sys.modules, "hvac", SimpleNamespace(Client=DummyClient))

    secrets = load_vault_secrets(
        {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_ROLE_ID": "role",
            "VAULT_SECRET_ID": "secret",
        }
    )

    assert secrets["OPENROUTER_API_KEY"] == "role-key"
    assert dummy_approle.login_calls == [("role", "secret")]
    assert dummy_kv.read_calls == [("dragonscales", "secret")]
