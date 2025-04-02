"""
Tests for message formatter functionality in Enterprise AI.

This file tests the formatting capabilities for different message types and content,
ensuring that messages are properly formatted for different output formats.
"""

import html
import sys
import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
import base64
import re

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import message classes
from enterprise_ai.schema import Message, Role  # noqa: E402
from enterprise_ai.message.constants import (  # noqa: E402
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_CODE,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_MARKDOWN,
)

# Import formatter module
from enterprise_ai.message.formatter import (  # noqa: E402
    MessageFormatter,
    PlainTextFormatter,
    MarkdownFormatter,
    HTMLFormatter,
    ConsoleFormatter,
    FormatterRegistry,
    format_message,
    format_messages,
    get_formatter,
    register_formatter,
    message_to_html,
    message_to_markdown,
)


# Mock enhanced message classes
class MockTextContent:
    def __init__(self, text):
        self.text = text
        self.content_type = CONTENT_TYPE_TEXT

    def get_content_type(self):
        return CONTENT_TYPE_TEXT

    def to_string(self):
        return self.text

    def to_dict(self):
        return {"content_type": CONTENT_TYPE_TEXT, "text": self.text}


class MockCodeContent:
    def __init__(self, code, language):
        self.code = code
        self.language = language
        self.content_type = CONTENT_TYPE_CODE

    def get_content_type(self):
        return CONTENT_TYPE_CODE

    def to_string(self):
        return f"```{self.language}\n{self.code}\n```"

    def to_dict(self):
        return {
            "content_type": CONTENT_TYPE_CODE,
            "code": self.code,
            "language": self.language,
        }


class MockImageContent:
    def __init__(self, data, format="png", alt_text=None):
        self.data = data
        self.format = format
        self.alt_text = alt_text
        self.content_type = CONTENT_TYPE_IMAGE

    def get_content_type(self):
        return CONTENT_TYPE_IMAGE

    def to_string(self):
        if self.alt_text:
            return f"[Image: {self.alt_text}]"
        return "[Image]"

    def to_dict(self):
        return {
            "content_type": CONTENT_TYPE_IMAGE,
            "data": self.data,
            "format": self.format,
            "alt_text": self.alt_text,
        }


class MockEnhancedMessage(Message):
    """Mock enhanced message for testing formatters."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_objects = []

    def add_content(self, content):
        self.content_objects.append(content)


# Test fixtures
@pytest.fixture
def text_message():
    """Create a simple text message."""
    return Message(role=Role.USER, content="Hello, this is a test message.")


@pytest.fixture
def code_message():
    """Create a message with code block."""
    content = """Here's a Python function:
```python
def greet(name):
    return f"Hello, {name}!"
```
This function returns a greeting."""
    return Message(role=Role.ASSISTANT, content=content)


@pytest.fixture
def tool_message():
    """Create a message with tool call."""
    from enterprise_ai.schema import ToolCall, Function

    tool_call = ToolCall(
        id="call_123",
        type="function",
        function=Function(
            name="get_weather", arguments='{"location": "San Francisco", "unit": "celsius"}'
        ),
    )

    return Message(
        role=Role.ASSISTANT, content="I'll check the weather for you.", tool_calls=[tool_call]
    )


@pytest.fixture
def image_message():
    """Create a message with base64 image."""
    # Simple 1x1 transparent PNG as base64
    base64_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

    return Message(role=Role.USER, content="Here's an image:", base64_image=base64_image)


@pytest.fixture
def enhanced_message():
    """Create a mock enhanced message with multiple content types."""
    message = MagicMock()
    message.role = Role.ASSISTANT
    message.content = "This is a message with multiple content types."
    message.content_objects = [
        MockTextContent("This is some text content."),
        MockCodeContent("print('Hello, world!')", "python"),
        MockImageContent(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
            alt_text="Sample image",
        ),
    ]
    # Either don't set a name or explicitly set to None
    message.name = None
    return message


@pytest.fixture
def message_conversation(text_message, code_message, tool_message):
    """Create a conversation with multiple messages."""
    system_message = Message(role=Role.SYSTEM, content="You are a helpful assistant.")

    return [system_message, text_message, code_message, tool_message]


# Tests for base formatter
def test_base_formatter_message(text_message):
    """Test base formatter with simple message."""
    formatter = MessageFormatter()
    result = formatter.format_message(text_message)

    assert "[USER]" in result
    assert text_message.content in result


def test_base_formatter_enhanced_message(enhanced_message):
    """Test base formatter with enhanced message."""
    formatter = MessageFormatter()
    result = formatter.format_enhanced_message(enhanced_message)

    assert "[ASSISTANT]" in result
    assert "This is some text content." in result
    assert "print('Hello, world!')" in result
    assert "Sample image" in result


def test_base_formatter_content():
    """Test base formatter with different content types."""
    formatter = MessageFormatter()

    text_content = MockTextContent("This is text.")
    code_content = MockCodeContent("console.log('test')", "javascript")
    image_content = MockImageContent("base64data", alt_text="Test image")

    text_result = formatter.format_content(text_content)
    code_result = formatter.format_content(code_content)
    image_result = formatter.format_content(image_content)

    assert text_result == "This is text."
    assert "javascript" in code_result
    assert "console.log('test')" in code_result
    assert "Test image" in image_result


def test_base_formatter_messages(message_conversation):
    """Test base formatter with multiple messages."""
    formatter = MessageFormatter()
    result = formatter.format_messages(message_conversation)

    assert "[SYSTEM]" in result
    assert "[USER]" in result
    assert "[ASSISTANT]" in result
    assert "You are a helpful assistant." in result
    assert "Hello, this is a test message." in result


# Tests for plain text formatter
def test_plain_text_formatter_message(code_message):
    """Test plain text formatter with code message."""
    formatter = PlainTextFormatter()
    result = formatter.format_message(code_message)

    assert "assistant:" in result
    assert "Here's a Python function:" in result
    assert "def greet(name):" in result
    assert "```" not in result  # Markdown markers should be stripped


def test_plain_text_formatter_enhanced_message(enhanced_message):
    """Test plain text formatter with enhanced message."""
    formatter = PlainTextFormatter()
    result = formatter.format_enhanced_message(enhanced_message)

    assert "assistant:" in result
    assert "This is some text content." in result
    assert "print('Hello, world!')" in result
    assert "[Image: Sample image]" in result
    assert "```" not in result  # Markdown markers should be stripped


def test_plain_text_formatter_strip_markdown():
    """Test stripping markdown formatting."""
    formatter = PlainTextFormatter()
    markdown_text = """# Heading
    
This is **bold** and *italic* text.

- List item 1
- List item 2

> A blockquote

[A link](https://example.com)
"""

    result = formatter._strip_markdown(markdown_text)

    assert "Heading" in result
    assert "bold" in result and "italic" in result
    assert "**" not in result
    assert "*" not in result
    assert "-" not in result or "- List" not in result
    assert ">" not in result
    assert "A link" in result
    assert "https://example.com" not in result
    assert "[" not in result and "]" not in result


# Tests for markdown formatter
def test_markdown_formatter_message(text_message):
    """Test markdown formatter with text message."""
    formatter = MarkdownFormatter()
    result = formatter.format_message(text_message)

    assert "**USER**" in result
    assert text_message.content in result


def test_markdown_formatter_code_message(code_message):
    """Test markdown formatter with code message."""
    formatter = MarkdownFormatter()
    result = formatter.format_message(code_message)

    assert "**ASSISTANT**" in result
    assert "```python" in result
    assert "def greet(name):" in result
    assert "```" in result


def test_markdown_formatter_tool_message(tool_message):
    """Test markdown formatter with tool call message."""
    formatter = MarkdownFormatter()
    result = formatter.format_message(tool_message)

    assert "**ASSISTANT**" in result
    assert "**Function Call:**" in result
    assert "`get_weather`" in result
    assert "```json" in result
    assert '"location": "San Francisco"' in result


def test_markdown_formatter_conversation(message_conversation):
    """Test markdown formatter with conversation."""
    formatter = MarkdownFormatter()
    result = formatter.format_messages(message_conversation)

    assert "**SYSTEM**" in result
    assert "**USER**" in result
    assert "**ASSISTANT**" in result
    assert "---" in result  # Separator between messages


# Tests for HTML formatter
def test_html_formatter_message(text_message):
    """Test HTML formatter with text message."""
    formatter = HTMLFormatter()
    result = formatter.format_message(text_message)

    assert '<div class="message message-user">' in result
    assert '<span class="message-role">USER</span>' in result
    assert '<div class="message-content">' in result
    assert text_message.content in result


def test_html_formatter_code_message(code_message):
    """Test HTML formatter with code message."""
    formatter = HTMLFormatter()
    result = formatter.format_message(code_message)

    assert '<div class="message message-assistant">' in result
    assert '<pre><code class="language-python">' in result
    assert "def greet(name):" in result
    assert "</code></pre>" in result


def test_html_formatter_image_message(image_message):
    """Test HTML formatter with image message."""
    formatter = HTMLFormatter()
    result = formatter.format_message(image_message)

    assert '<div class="message message-user">' in result
    assert '<div class="message-image">' in result
    assert '<img src="data:image/png;base64,' in result


def test_html_formatter_enhanced_message(enhanced_message):
    """Test HTML formatter with enhanced message."""
    formatter = HTMLFormatter()
    result = formatter.format_enhanced_message(enhanced_message)
    decoded_result = html.unescape(result)

    assert '<div class="message message-assistant">' in result
    assert '<div class="content-text">' in result
    assert '<div class="content-code">' in result
    assert '<div class="content-image">' in result
    assert '<code class="language-python">' in result
    assert "print('Hello, world!')" in decoded_result


def test_html_formatter_full_document(message_conversation):
    """Test generating a complete HTML document."""
    formatter = HTMLFormatter()
    result = formatter.get_full_html_document(message_conversation, "Test Conversation")

    assert "<!DOCTYPE html>" in result
    assert "<html>" in result
    assert "<head>" in result
    assert "<title>Test Conversation</title>" in result
    assert "<style>" in result
    assert "<body>" in result
    assert "<h1>Test Conversation</h1>" in result
    assert '<div class="conversation">' in result


def test_html_formatter_escape_html():
    """Test HTML escaping."""
    formatter = HTMLFormatter()
    html_text = "This has <tags> & special \"characters\" that need 'escaping'"

    result = formatter._escape_html(html_text)

    assert "&lt;tags&gt;" in result
    assert "&amp;" in result
    assert "&quot;" in result
    assert "&#39;" in result


# Tests for console formatter
def test_console_formatter_with_colors():
    """Test console formatter with colors enabled."""
    formatter = ConsoleFormatter(use_colors=True)
    message = Message(role=Role.SYSTEM, content="System message")

    result = formatter.format_message(message)

    assert "\033[" in result  # ANSI escape codes should be present
    assert "[SYSTEM]" in result
    assert "System message" in result


def test_console_formatter_without_colors():
    """Test console formatter with colors disabled."""
    formatter = ConsoleFormatter(use_colors=False)
    message = Message(role=Role.SYSTEM, content="System message")

    result = formatter.format_message(message)

    assert "\033[" not in result  # No ANSI escape codes
    assert "[SYSTEM]" in result
    assert "System message" in result


def test_console_formatter_tool_calls(tool_message):
    """Test console formatter with tool calls."""
    formatter = ConsoleFormatter(use_colors=False)
    result = formatter.format_message(tool_message)

    assert "[ASSISTANT]" in result
    assert "I'll check the weather for you." in result
    assert "[Tool Calls]" in result
    assert "Function: get_weather" in result
    assert "Arguments:" in result
    assert '"location": "San Francisco"' in result


# Tests for formatter registry
def test_formatter_registry_get_default():
    """Test getting default formatter from registry."""
    formatter = FormatterRegistry.get_formatter()
    assert isinstance(formatter, MessageFormatter)


def test_formatter_registry_get_by_name():
    """Test getting formatters by name from registry."""
    plain_formatter = FormatterRegistry.get_formatter("plain")
    markdown_formatter = FormatterRegistry.get_formatter("markdown")
    html_formatter = FormatterRegistry.get_formatter("html")
    console_formatter = FormatterRegistry.get_formatter("console")

    assert isinstance(plain_formatter, PlainTextFormatter)
    assert isinstance(markdown_formatter, MarkdownFormatter)
    assert isinstance(html_formatter, HTMLFormatter)
    assert isinstance(console_formatter, ConsoleFormatter)


def test_formatter_registry_get_unknown():
    """Test getting unknown formatter falls back to default."""
    formatter = FormatterRegistry.get_formatter("nonexistent")
    assert isinstance(formatter, MessageFormatter)


def test_formatter_registry_register_custom():
    """Test registering a custom formatter."""
    custom_formatter = MessageFormatter()
    FormatterRegistry.register_formatter("custom", custom_formatter)

    retrieved = FormatterRegistry.get_formatter("custom")
    assert retrieved is custom_formatter


def test_formatter_registry_format_message():
    """Test formatting message through registry."""
    message = Message(role=Role.USER, content="Test message")

    result = FormatterRegistry.format_message(message, "markdown")

    assert "**USER**" in result
    assert "Test message" in result


# Tests for helper functions
def test_format_message_helper():
    """Test format_message helper function."""
    message = Message(role=Role.USER, content="Test message")

    result = format_message(message, "markdown")

    assert "**USER**" in result
    assert "Test message" in result


def test_format_messages_helper():
    """Test format_messages helper function."""
    messages = [
        Message(role=Role.USER, content="Hello"),
        Message(role=Role.ASSISTANT, content="Hi there"),
    ]

    result = format_messages(messages, "markdown")

    assert "**USER**" in result
    assert "**ASSISTANT**" in result
    assert "Hello" in result
    assert "Hi there" in result


def test_get_formatter_helper():
    """Test get_formatter helper function."""
    formatter = get_formatter("html")
    assert isinstance(formatter, HTMLFormatter)


def test_register_formatter_helper():
    """Test register_formatter helper function."""
    custom_formatter = MessageFormatter()
    register_formatter("test_custom", custom_formatter)

    retrieved = get_formatter("test_custom")
    assert retrieved is custom_formatter


def test_message_to_html_helper():
    """Test message_to_html helper function."""
    message = Message(role=Role.ASSISTANT, content="Hello world")

    result = message_to_html(message)

    assert '<div class="message message-assistant">' in result
    assert '<span class="message-role">ASSISTANT</span>' in result
    assert "Hello world" in result


def test_message_to_markdown_helper():
    """Test message_to_markdown helper function."""
    message = Message(role=Role.ASSISTANT, content="Hello world")

    result = message_to_markdown(message)

    assert "**ASSISTANT**" in result
    assert "Hello world" in result
