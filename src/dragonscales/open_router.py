"""OpenRouter client factory using the OpenAI SDK."""

from __future__ import annotations

import os
from typing import Mapping

from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def create_openrouter_client(
    api_key: str | None = None, env: Mapping[str, str] | None = None
) -> OpenAI:
    """
    Create an OpenAI client configured for OpenRouter.

    If `api_key` is not provided, the function will attempt to read
    OPENROUTER_API_KEY from the provided env mapping or os.environ.
    """
    source = os.environ if env is None else env
    key = api_key or source.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY is not set")
    return OpenAI(api_key=key, base_url=OPENROUTER_BASE_URL)
