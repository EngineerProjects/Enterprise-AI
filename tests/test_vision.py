"""Tests for vision / ImageBlock support in providers."""
from __future__ import annotations

from enterprise_ai.schema import ImageBlock, Message, TextBlock
from enterprise_ai.schema.message import Role


def _make_anthropic() -> object:
    from enterprise_ai.providers.anthropic import AnthropicProvider
    return AnthropicProvider.__new__(AnthropicProvider)


def _make_openai() -> object:
    from enterprise_ai.providers.openai import OpenAIProvider
    return OpenAIProvider.__new__(OpenAIProvider)


# ── Anthropic ─────────────────────────────────────────────────────────────────

def test_anthropic_plain_text_user_message():
    provider = _make_anthropic()
    msg = Message.user("hello")
    _, converted = provider._to_anthropic_messages([msg])
    assert converted[0]["content"] == "hello"


def test_anthropic_user_with_url_image():
    provider = _make_anthropic()
    msg = Message(
        role=Role.user,
        content=[
            TextBlock(text="What is in this image?"),
            ImageBlock(source={"type": "url", "url": "https://example.com/img.jpg"}),
        ],
    )
    _, converted = provider._to_anthropic_messages([msg])
    parts = converted[0]["content"]
    assert parts[0] == {"type": "text", "text": "What is in this image?"}
    assert parts[1] == {"type": "image", "source": {"type": "url", "url": "https://example.com/img.jpg"}}


def test_anthropic_user_with_base64_image():
    provider = _make_anthropic()
    msg = Message(
        role=Role.user,
        content=[
            ImageBlock(source={"type": "base64", "media_type": "image/png", "data": "abc123"}),
        ],
    )
    _, converted = provider._to_anthropic_messages([msg])
    parts = converted[0]["content"]
    assert parts[0]["type"] == "image"
    assert parts[0]["source"]["type"] == "base64"
    assert parts[0]["source"]["media_type"] == "image/png"
    assert parts[0]["source"]["data"] == "abc123"


def test_anthropic_image_only_no_text_block():
    provider = _make_anthropic()
    msg = Message(
        role=Role.user,
        content=[ImageBlock(source={"type": "url", "url": "http://x.com/img.png"})],
    )
    _, converted = provider._to_anthropic_messages([msg])
    parts = converted[0]["content"]
    assert len(parts) == 1
    assert parts[0]["type"] == "image"


def test_anthropic_empty_text_block_filtered():
    provider = _make_anthropic()
    msg = Message(
        role=Role.user,
        content=[
            TextBlock(text=""),  # empty → filtered
            ImageBlock(source={"type": "url", "url": "http://x.com/img.png"}),
        ],
    )
    _, converted = provider._to_anthropic_messages([msg])
    parts = converted[0]["content"]
    # Only the image block (empty text filtered)
    assert all(p["type"] == "image" for p in parts)


# ── OpenAI ────────────────────────────────────────────────────────────────────

def test_openai_plain_text_user_message():
    provider = _make_openai()
    msg = Message.user("hello")
    converted = provider._to_openai_messages([msg])
    assert converted[0]["content"] == "hello"


def test_openai_user_with_url_image():
    provider = _make_openai()
    msg = Message(
        role=Role.user,
        content=[
            TextBlock(text="Describe this"),
            ImageBlock(source={"type": "url", "url": "https://example.com/photo.jpg"}),
        ],
    )
    converted = provider._to_openai_messages([msg])
    parts = converted[0]["content"]
    assert parts[0] == {"type": "text", "text": "Describe this"}
    assert parts[1] == {"type": "image_url", "image_url": {"url": "https://example.com/photo.jpg"}}


def test_openai_user_with_base64_image():
    provider = _make_openai()
    msg = Message(
        role=Role.user,
        content=[
            ImageBlock(source={"type": "base64", "media_type": "image/jpeg", "data": "xyz789"}),
        ],
    )
    converted = provider._to_openai_messages([msg])
    parts = converted[0]["content"]
    assert parts[0]["type"] == "image_url"
    assert parts[0]["image_url"]["url"] == "data:image/jpeg;base64,xyz789"


def test_openai_base64_default_media_type():
    provider = _make_openai()
    msg = Message(
        role=Role.user,
        content=[ImageBlock(source={"type": "base64", "data": "abc"})],  # no media_type
    )
    converted = provider._to_openai_messages([msg])
    url = converted[0]["content"][0]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")


def test_openai_multiple_images():
    provider = _make_openai()
    msg = Message(
        role=Role.user,
        content=[
            ImageBlock(source={"type": "url", "url": "http://a.com/1.jpg"}),
            ImageBlock(source={"type": "url", "url": "http://a.com/2.jpg"}),
        ],
    )
    converted = provider._to_openai_messages([msg])
    parts = converted[0]["content"]
    assert len(parts) == 2
    assert all(p["type"] == "image_url" for p in parts)
