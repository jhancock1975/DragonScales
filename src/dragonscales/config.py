"""Configuration loader that pulls credentials from Vault or the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Mapping, MutableMapping


@dataclass
class Settings:
    openrouter_api_key: str
    cache_url: str | None = None


def build_cache_url(source: Mapping[str, str]) -> str | None:
    """Build a Redis URL from individual parts when a full URL is not provided."""
    if cache_url := source.get("CACHE_URL"):
        return cache_url

    password = source.get("REDIS_PASSWORD")
    if not password:
        return None

    username = source.get("REDIS_USERNAME", "default")
    host = source.get("REDIS_HOST", "cache")
    port = source.get("REDIS_PORT", "6379")
    db = source.get("REDIS_DB", "0")

    auth = f"{username}:{password}@"
    return f"redis://{auth}{host}:{port}/{db}"


def load_vault_secrets(env: Mapping[str, str]) -> dict[str, str]:
    """Load secrets from a HashiCorp Vault KV v2 path."""
    vault_addr = env.get("VAULT_ADDR")
    if not vault_addr:
        return {}

    try:
        import hvac  # type: ignore
    except ImportError as exc:
        raise RuntimeError("hvac is required for Vault access; install the 'vault' extra") from exc

    client = hvac.Client(url=vault_addr)

    token = env.get("VAULT_TOKEN")
    role_id = env.get("VAULT_ROLE_ID")
    secret_id = env.get("VAULT_SECRET_ID")
    if token:
        client.token = token
    elif role_id and secret_id:
        client.auth.approle.login(role_id=role_id, secret_id=secret_id)
    else:
        raise RuntimeError("Vault credentials not provided (VAULT_TOKEN or VAULT_ROLE_ID/VAULT_SECRET_ID)")

    path = env.get("VAULT_SECRET_PATH", "dragonscales")
    mount_point = env.get("VAULT_KV_MOUNT", "secret")

    secret = client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount_point)  # type: ignore[attr-defined]
    data = secret.get("data", {}).get("data", {}) if secret else {}
    return {k: str(v) for k, v in data.items()}


def load_settings(
    api_key: str | None = None,
    cache_url: str | None = None,
    env: Mapping[str, str] | None = None,
    vault_loader: Callable[[Mapping[str, str]], Mapping[str, str]] = load_vault_secrets,
) -> Settings:
    """Load settings using Vault first, with environment overrides."""
    source: MutableMapping[str, str | None] = dict(os.environ if env is None else env)
    if api_key is not None:
        source["OPENROUTER_API_KEY"] = api_key
    if cache_url is not None:
        source["CACHE_URL"] = cache_url

    vault_secrets = vault_loader(source)
    merged: dict[str, str] = {**vault_secrets, **{k: v for k, v in source.items() if v is not None}}

    openrouter_api_key = merged.get("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is not set in environment or Vault")

    cache_url_value = merged.get("CACHE_URL") or build_cache_url(merged)
    return Settings(openrouter_api_key=openrouter_api_key, cache_url=cache_url_value)
