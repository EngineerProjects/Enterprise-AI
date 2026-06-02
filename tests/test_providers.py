"""
Unit tests for provider factory and Bedrock message conversion.
No real API calls — tests factory routing and Bedrock format translation.
"""
import pytest

from enterprise_ai.providers.anthropic import AnthropicProvider
from enterprise_ai.providers.factory import _OPENAI_COMPATIBLE, create_provider
from enterprise_ai.providers.openai import OpenAIProvider
from enterprise_ai.schema import Message, ToolCall, ToolSchema

# ---------------------------------------------------------------------------
# Factory — provider routing
# ---------------------------------------------------------------------------

def test_factory_anthropic():
    provider = create_provider("anthropic", model="claude-haiku-4-5-20251001")
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-haiku-4-5-20251001"


_DUMMY_KEY = "sk-test-dummy-key-for-unit-tests"


def test_factory_openai():
    provider = create_provider("openai", model="gpt-4o-mini", api_key=_DUMMY_KEY)
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "gpt-4o-mini"


def test_factory_openai_compatible_providers():
    """All OpenAI-compatible providers instantiate correctly with a dummy key."""
    compatible = [name for name in _OPENAI_COMPATIBLE if name != "openai"]
    for name in compatible:
        # ollama doesn't need a real key; others get a dummy
        kwargs = {} if name == "ollama" else {"api_key": _DUMMY_KEY}
        provider = create_provider(name, **kwargs)
        assert isinstance(provider, OpenAIProvider), f"{name} should return OpenAIProvider"
        assert provider.model  # has a default model


def test_factory_mistral_default_model():
    provider = create_provider("mistral", api_key=_DUMMY_KEY)
    assert "mistral" in provider.model.lower()


def test_factory_gemini_default_model():
    provider = create_provider("gemini", api_key=_DUMMY_KEY)
    assert "gemini" in provider.model.lower()


def test_factory_deepseek_default_model():
    provider = create_provider("deepseek", api_key=_DUMMY_KEY)
    assert "deepseek" in provider.model.lower()


def test_factory_groq_default_model():
    provider = create_provider("groq", api_key=_DUMMY_KEY)
    assert provider.model  # has some default


def test_factory_ollama_uses_ollama_api_key():
    """Ollama doesn't need a real key — factory injects 'ollama' as placeholder."""
    provider = create_provider("ollama", model="llama3.1")
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "llama3.1"


def test_factory_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider("nonexistent_provider_xyz")


def test_factory_custom_model_overrides_default():
    provider = create_provider("groq", model="llama-3.1-8b-instant", api_key=_DUMMY_KEY)
    assert provider.model == "llama-3.1-8b-instant"


def test_factory_error_message_lists_all_supported():
    try:
        create_provider("invalid")
    except ValueError as e:
        msg = str(e)
        assert "anthropic" in msg
        assert "bedrock" in msg
        assert "mistral" in msg
        assert "gemini" in msg


# ---------------------------------------------------------------------------
# Bedrock — message format conversion (no boto3 needed)
# ---------------------------------------------------------------------------

class MockBedrockClient:
    """Minimal mock to instantiate BedrockProvider without boto3."""
    def converse(self, **kwargs): return {}
    def converse_stream(self, **kwargs): return {"stream": []}


def make_bedrock_provider():
    """Create a BedrockProvider with a mock client."""
    from enterprise_ai.providers.bedrock import BedrockProvider
    provider = object.__new__(BedrockProvider)
    provider._model = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    provider._client = MockBedrockClient()
    return provider


def test_bedrock_message_conversion_user():
    provider = make_bedrock_provider()
    messages = [Message.user("Hello, world!")]
    bedrock_msgs, system = provider._to_bedrock_messages(messages)

    assert system == ""
    assert len(bedrock_msgs) == 1
    assert bedrock_msgs[0]["role"] == "user"
    assert bedrock_msgs[0]["content"][0]["text"] == "Hello, world!"


def test_bedrock_message_conversion_system_extracted():
    provider = make_bedrock_provider()
    messages = [
        Message.system("You are a helpful assistant."),
        Message.user("Hello!"),
    ]
    bedrock_msgs, system = provider._to_bedrock_messages(messages)

    assert system == "You are a helpful assistant."
    assert len(bedrock_msgs) == 1  # system removed from messages list


def test_bedrock_message_conversion_assistant_with_tool_call():
    provider = make_bedrock_provider()
    tc = ToolCall(id="call-123", name="get_weather", input={"city": "Paris"})
    messages = [
        Message.user("What's the weather?"),
        Message.assistant("Let me check.", tool_calls=[tc]),
    ]
    bedrock_msgs, _ = provider._to_bedrock_messages(messages)

    assistant_msg = bedrock_msgs[1]
    assert assistant_msg["role"] == "assistant"
    tool_use_block = next(b for b in assistant_msg["content"] if "toolUse" in b)
    assert tool_use_block["toolUse"]["toolUseId"] == "call-123"
    assert tool_use_block["toolUse"]["name"] == "get_weather"
    assert tool_use_block["toolUse"]["input"] == {"city": "Paris"}


def test_bedrock_message_conversion_tool_result():
    provider = make_bedrock_provider()
    messages = [
        Message.user("What's the weather?"),
        Message.assistant("", tool_calls=[ToolCall(id="call-1", name="weather", input={})]),
        Message.tool_result("call-1", "Sunny, 22°C", name="weather"),
    ]
    bedrock_msgs, _ = provider._to_bedrock_messages(messages)

    # Tool result should be in a user message
    last_msg = bedrock_msgs[-1]
    assert last_msg["role"] == "user"
    tool_result_block = next(b for b in last_msg["content"] if "toolResult" in b)
    assert tool_result_block["toolResult"]["toolUseId"] == "call-1"
    assert "Sunny" in tool_result_block["toolResult"]["content"][0]["text"]


def test_bedrock_tool_schema_conversion():
    provider = make_bedrock_provider()
    tools = [
        ToolSchema(
            name="get_weather",
            description="Get weather for a city",
            input_schema={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        )
    ]
    tool_config = provider._to_bedrock_tools(tools)

    assert "tools" in tool_config
    spec = tool_config["tools"][0]["toolSpec"]
    assert spec["name"] == "get_weather"
    assert spec["description"] == "Get weather for a city"
    assert spec["inputSchema"]["json"]["type"] == "object"


def test_bedrock_parse_converse_response_text():
    provider = make_bedrock_provider()
    response = {
        "output": {
            "message": {
                "content": [{"text": "Here is the answer."}]
            }
        },
        "usage": {"inputTokens": 10, "outputTokens": 5},
        "stopReason": "end_turn",
    }
    result = provider._parse_converse_response(response)
    assert result.content == "Here is the answer."
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert not result.has_tool_calls


def test_bedrock_parse_converse_response_tool_call():
    provider = make_bedrock_provider()
    response = {
        "output": {
            "message": {
                "content": [
                    {"text": "Let me check."},
                    {"toolUse": {"toolUseId": "id-1", "name": "search", "input": {"query": "test"}}},
                ]
            }
        },
        "usage": {"inputTokens": 20, "outputTokens": 8},
        "stopReason": "tool_use",
    }
    result = provider._parse_converse_response(response)
    assert result.content == "Let me check."
    assert result.has_tool_calls
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search"
    assert result.tool_calls[0].input == {"query": "test"}
