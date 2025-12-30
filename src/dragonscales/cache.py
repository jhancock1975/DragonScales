"""Cache backends for the Dragon model fetcher."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


class CacheBackend(Protocol):
    """Minimal cache interface for storing Python objects with an optional TTL."""

    def get(self, key: str) -> Any | None:  # pragma: no cover - protocol
        ...

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:  # pragma: no cover - protocol
        ...


class InMemoryCache(CacheBackend):
    """Simple in-memory cache with per-key TTL."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[datetime | None, Any]] = {}

    def get(self, key: str) -> Any | None:
        expires_at, value = self._entries.get(key, (None, None))
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires_at: datetime | None = None
        if ttl_seconds is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._entries[key] = (expires_at, value)


class RedisCache(CacheBackend):
    """Redis-backed cache that pickles Python objects."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def get(self, key: str) -> Any | None:
        raw = self.client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        payload = json.dumps(value, default=self._json_default).encode("utf-8")
        if ttl_seconds:
            self.client.setex(key, ttl_seconds, payload)
        else:
            self.client.set(key, payload)

    @staticmethod
    def _json_default(obj: Any) -> Any:
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)


def redis_cache_from_url(url: str) -> RedisCache:
    """Create a Redis-backed cache from a URL."""
    try:
        import redis  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised in runtime
        raise RuntimeError("Install the 'redis' extra to use RedisCache") from exc

    client = redis.Redis.from_url(url)  # type: ignore[call-arg]
    return RedisCache(client)
