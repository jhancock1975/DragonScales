import pytest

from dragonscales.open_router import OPENROUTER_BASE_URL, create_openrouter_client


def test_from_env_raises_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(ValueError):
        create_openrouter_client()


def test_client_uses_openrouter_base_url():
    client = create_openrouter_client(api_key="abc123")

    assert client.api_key == "abc123"
    assert str(client.base_url).rstrip("/") == OPENROUTER_BASE_URL
