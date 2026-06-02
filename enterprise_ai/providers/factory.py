from __future__ import annotations

from typing import Any

from enterprise_ai.providers.base import Provider


def create_provider(name: str, model: str | None = None, **kwargs: Any) -> Provider:
    """
    Factory shorthand:
        create_provider("anthropic", model="claude-opus-4-8")
        create_provider("openai", model="gpt-4o")
        create_provider("openrouter", model="meta-llama/llama-3-70b")
        create_provider("ollama", model="llama3.1")
    """
    name = name.lower()

    if name == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(model=model or "claude-opus-4-8", **kwargs)

    if name in ("openai", "openrouter", "ollama"):
        from .openai import OpenAIProvider
        base_urls = {
            "openrouter": "https://openrouter.ai/api/v1",
            "ollama": "http://localhost:11434/v1",
        }
        defaults = {
            "openai": "gpt-4o",
            "openrouter": "meta-llama/llama-3-70b-instruct",
            "ollama": "llama3.1",
        }
        return OpenAIProvider(
            model=model or defaults[name],
            base_url=base_urls.get(name),
            **kwargs,
        )

    raise ValueError(f"Unknown provider: {name!r}. Supported: anthropic, openai, openrouter, ollama")
