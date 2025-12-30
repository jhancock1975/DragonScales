from openai import OpenAI

from dragonscales.cache import CacheBackend, redis_cache_from_url
from dragonscales.config import load_settings
from dragonscales.dragon import Dragon
from dragonscales.open_router import create_openrouter_client


def build_dragon(
    api_key: str | None = None,
    cache_url: str | None = None,
    env: dict[str, str] | None = None,
) -> Dragon:
    """Construct a Dragon instance with optional persistent cache."""
    settings = load_settings(api_key=api_key, cache_url=cache_url, env=env)
    client = create_openrouter_client(api_key=settings.openrouter_api_key, env=env)
    cache: CacheBackend | None = None
    if settings.cache_url:
        cache = redis_cache_from_url(settings.cache_url)

    return Dragon(client, cache=cache)


def main(api_key: str | None = None, cache_url: str | None = None) -> Dragon:
    """Entrypoint for DragonScales; prepares a Dragon instance with optional cache."""
    dragon = build_dragon(api_key=api_key, cache_url=cache_url)
    print("dragonscales")
    return dragon


if __name__ == "__main__":
    main()
