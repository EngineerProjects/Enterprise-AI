from __future__ import annotations

import os
from typing import Any

from enterprise_ai.providers.base import Provider

# Providers that use the OpenAI-compatible API (same SDK, different base_url + key)
_OPENAI_COMPATIBLE: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "",
        "model": "gpt-4o",
        "key_env": "OPENAI_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3-70b-instruct",
        "key_env": "OPENROUTER_API_KEY",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.1",
        "key_env": "",  # no key needed
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-large-latest",
        "key_env": "MISTRAL_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
        "key_env": "GOOGLE_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_env": "GROQ_API_KEY",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-3",
        "key_env": "XAI_API_KEY",
    },
}


def create_provider(name: str, model: str | None = None, **kwargs: Any) -> Provider:
    """
    Factory shorthand — create any supported provider by name.

    OpenAI-compatible (no extra deps):
        create_provider("anthropic",  model="claude-opus-4-8")
        create_provider("openai",     model="gpt-4o")
        create_provider("openrouter", model="meta-llama/llama-3-70b-instruct")
        create_provider("ollama",     model="llama3.1")
        create_provider("mistral",    model="mistral-large-latest")
        create_provider("gemini",     model="gemini-2.0-flash")
        create_provider("deepseek",   model="deepseek-chat")
        create_provider("groq",       model="llama-3.3-70b-versatile")
        create_provider("xai",        model="grok-3")

    Requires extras:
        create_provider("bedrock",    model="anthropic.claude-3-5-sonnet-20241022-v2:0")
        # pip install enterprise-ai[bedrock]

    API keys are read from environment variables automatically (see _OPENAI_COMPATIBLE).
    You can also pass api_key= explicitly as a kwarg.
    """
    name = name.lower()

    # Anthropic — native SDK
    if name == "anthropic":
        from enterprise_ai.providers.anthropic import AnthropicProvider
        return AnthropicProvider(model=model or "claude-opus-4-8", **kwargs)

    # AWS Bedrock — boto3
    if name == "bedrock":
        from enterprise_ai.providers.bedrock import BedrockProvider
        return BedrockProvider(
            model=model or "anthropic.claude-3-5-sonnet-20241022-v2:0",
            **kwargs,
        )

    # OpenAI-compatible providers
    if name in _OPENAI_COMPATIBLE:
        from enterprise_ai.providers.openai import OpenAIProvider
        cfg = _OPENAI_COMPATIBLE[name]
        resolved_model = model or cfg["model"]
        base_url = cfg["base_url"] or None

        # Auto-resolve API key from env if not passed explicitly
        if "api_key" not in kwargs and cfg["key_env"]:
            env_key = os.environ.get(cfg["key_env"])
            if env_key:
                kwargs["api_key"] = env_key
        # Ollama doesn't need a real key
        if name == "ollama" and "api_key" not in kwargs:
            kwargs["api_key"] = "ollama"

        return OpenAIProvider(model=resolved_model, base_url=base_url, **kwargs)

    supported = sorted(list(_OPENAI_COMPATIBLE.keys()) + ["anthropic", "bedrock"])
    raise ValueError(
        f"Unknown provider: {name!r}. Supported: {', '.join(supported)}"
    )
