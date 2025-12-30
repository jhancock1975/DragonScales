"""Dragon object that knows how to fetch free OpenRouter models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from dragonscales.cache import CacheBackend


class Dragon:
    """Caches free model listings from OpenRouter with a refresh TTL."""

    def __init__(
        self,
        client: Any,
        ttl_seconds: int = 3600,
        cache: CacheBackend | None = None,
        cache_key: str = "dragon:free_models",
    ) -> None:
        self.client = client
        self.ttl = timedelta(seconds=ttl_seconds)
        self.cache = cache
        self.cache_key = cache_key
        self._models: list[Any] | None = None
        self._last_refresh: datetime | None = None

    def refresh_models(self, force: bool = False) -> list[Any]:
        """Refresh the cached model list when stale or when forced."""
        now = self._now()
        if not force:
            cached_models = self._cached_models(now)
            if cached_models is not None:
                return cached_models

        self._models = self._fetch_free_models()
        self._last_refresh = now
        self._write_cache(self._models)
        return self._models

    def _fetch_free_models(self) -> list[Any]:
        """Retrieve free models from OpenRouter."""
        response = self.client.models.list()
        models = getattr(response, "data", response)
        return [model for model in models if self._is_free(model)]

    def _is_free(self, model: Any) -> bool:
        """Determine whether a model is free based on pricing metadata."""
        pricing = self._get_pricing(model)
        if pricing is None:
            return False

        prompt_price = self._price_value(pricing, "prompt")
        completion_price = self._price_value(pricing, "completion")
        if prompt_price is None or completion_price is None:
            return False

        return prompt_price == 0 and completion_price == 0

    def _get_pricing(self, model: Any) -> Mapping[str, Any] | None:
        if hasattr(model, "pricing"):
            return getattr(model, "pricing")
        if isinstance(model, Mapping):
            return model.get("pricing")
        return None

    def _price_value(self, pricing: Any, key: str) -> float | None:
        value: Any
        if isinstance(pricing, Mapping):
            value = pricing.get(key)
        else:
            value = getattr(pricing, key, None)

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _cached_models(self, now: datetime) -> list[Any] | None:
        if self.cache:
            cached = self.cache.get(self.cache_key)
            if cached is not None:
                self._models = cached
                self._last_refresh = now
                return cached

        if (
            self._models is not None
            and self._last_refresh is not None
            and now - self._last_refresh < self.ttl
        ):
            return self._models
        return None

    def _write_cache(self, models: list[Any]) -> None:
        if self.cache:
            ttl_seconds = int(self.ttl.total_seconds())
            self.cache.set(self.cache_key, models, ttl_seconds)
