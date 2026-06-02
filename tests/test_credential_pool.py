"""Tests for item 1: credential pool + key rotation."""
from __future__ import annotations

import pytest

from enterprise_ai.providers.credential_pool import CredentialPool


def test_single_key_current():
    pool = CredentialPool(["sk-1"])
    assert pool.current == "sk-1"


def test_single_key_rotate_exhausts_immediately():
    pool = CredentialPool(["sk-1"])
    pool.reset_round()
    assert pool.rotate() is True  # only 1 key — immediately exhausted


def test_two_keys_rotate_to_next():
    pool = CredentialPool(["sk-1", "sk-2"])
    pool.reset_round()
    assert pool.current == "sk-1"
    exhausted = pool.rotate()
    assert not exhausted
    assert pool.current == "sk-2"


def test_two_keys_second_rotate_exhausts():
    pool = CredentialPool(["sk-1", "sk-2"])
    pool.reset_round()
    pool.rotate()       # advance to sk-2
    exhausted = pool.rotate()
    assert exhausted is True


def test_three_keys_full_rotation():
    pool = CredentialPool(["sk-1", "sk-2", "sk-3"])
    pool.reset_round()
    assert not pool.rotate()  # sk-1 → sk-2
    assert not pool.rotate()  # sk-2 → sk-3
    assert pool.rotate()      # sk-3 → exhausted


def test_reset_round_allows_re_rotation():
    pool = CredentialPool(["sk-1", "sk-2"])
    pool.reset_round()
    pool.rotate()
    pool.rotate()       # exhausted

    # After reset, rotation starts fresh
    pool.reset_round()
    exhausted = pool.rotate()
    assert not exhausted


def test_pool_requires_at_least_one_key():
    with pytest.raises(ValueError):
        CredentialPool([])


def test_none_key_allowed():
    """None is a valid entry (means 'use env var')."""
    pool = CredentialPool([None])
    assert pool.current is None


def test_size_property():
    pool = CredentialPool(["a", "b", "c"])
    assert pool.size == 3


# ── Integration: AnthropicProvider rotates keys on 429 ───────────────────────

def test_anthropic_provider_accepts_api_keys_list():
    """AnthropicProvider can be instantiated with api_keys without error."""
    from unittest.mock import MagicMock, patch

    mock_client = MagicMock()
    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        from enterprise_ai.providers.anthropic import AnthropicProvider
        provider = AnthropicProvider(api_keys=["sk-1", "sk-2"])
        assert provider._pool.size == 2


def test_openai_provider_accepts_api_keys_list():
    """OpenAIProvider can be instantiated with api_keys without error."""
    from unittest.mock import MagicMock, patch

    mock_client = MagicMock()
    with patch("openai.AsyncOpenAI", return_value=mock_client):
        from enterprise_ai.providers.openai import OpenAIProvider
        provider = OpenAIProvider(api_keys=["sk-1", "sk-2"])
        assert provider._pool.size == 2


@pytest.mark.asyncio
async def test_anthropic_rotates_to_second_key_on_429():
    """On 429, provider silently rotates to the next key and retries."""
    from unittest.mock import MagicMock, patch

    from enterprise_ai.schema import Message

    rate_limit_exc = Exception("rate limited")
    rate_limit_exc.status_code = 429  # type: ignore[attr-defined]

    # First call raises 429, second call succeeds
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(type="text", text="hello")]
    mock_resp.usage = MagicMock(input_tokens=10, output_tokens=5)
    mock_resp.stop_reason = "end_turn"

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise rate_limit_exc
        return mock_resp

    mock_client = MagicMock()
    mock_client.messages.create = fake_create

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        from enterprise_ai.providers.anthropic import AnthropicProvider
        provider = AnthropicProvider(api_keys=["sk-1", "sk-2"])
        # Both clients point to the same mock in this test
        provider._clients = [mock_client, mock_client]

        result = await provider.complete([Message.user("hi")])
        assert result.content == "hello"
        assert call_count == 2  # tried first key (429), then second key (success)
