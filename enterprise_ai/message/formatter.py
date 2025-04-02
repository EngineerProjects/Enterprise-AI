"""
Message formatting utilities for Enterprise AI.

This module provides specialized formatters for rendering messages in different
formats and contexts, including console output, markdown, HTML, and other
presentation formats. These formatters work with both standard messages and
enhanced messages with mixed content types.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, Role
from enterprise_ai.types import MessageProtocol, ToolCallProtocol, RoleType
from enterprise_ai.message.constants import (
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_CODE,
    CONTENT_TYPE_MARKDOWN,
    CONTENT_TYPE_TOOL_CALL,
    CONTENT_TYPE_TOOL_RESULT,
    CONTENT_TYPE_FILE,
    CODE_BLOCK_START,
    CODE_BLOCK_END,
    BOLD_MARKER,
    ITALIC_MARKER,
    STRIKETHROUGH_MARKER,
    HEADING_MARKER,
    UNORDERED_LIST_MARKER,
    ORDERED_LIST_MARKER,
    BLOCKQUOTE_MARKER,
    LINK_FORMAT,
    IMAGE_FORMAT,
    MESSAGE_FORMAT_DEFAULT,
    MESSAGE_FORMAT_MARKDOWN,
    MESSAGE_FORMAT_HTML,
    MESSAGE_FORMAT_PLAIN,
)
from enterprise_ai.message.types import (
    ContentProtocol,
    MessageFormatValue,
    TextContent,
    ImageContent,
    CodeContent,
    MarkdownContent,
    ToolCallContent,
    ToolResultContent,
    FileContent,
)
from enterprise_ai.message.utils import (
    extract_code_blocks,
    extract_text_without_code_blocks,
    get_message_type,
)

# Initialize logger
logger = get_logger("message.formatter")


# -----------------------------------------------------------------------------
# Base Formatter
# -----------------------------------------------------------------------------


class MessageFormatter:
    """Base class for message formatters.

    This class provides common functionality for formatting messages and serves
    as the parent class for specialized formatters.
    """

    def format_message(self, message: MessageProtocol) -> str:
        """Format a message into a string representation.

        Args:
            message: The message to format

        Returns:
            Formatted message as a string
        """
        # Default implementation provides a simple role-based format
        role_str = f"[{message.role.upper()}]"
        content_str = message.content or ""

        # Add name if present
        if message.name:
            role_str = f"{role_str} ({message.name})"

        # Handle image in basic format
        if message.base64_image:
            content_str += "\n[Image included]"

        # Handle tool calls in basic format
        if message.tool_calls:
            tool_calls_str = "\n".join(
                [
                    f"Function: {tc.function.name}\nArguments: {tc.function.arguments}"
                    for tc in message.tool_calls
                ]
            )
            content_str += f"\n[Tool Calls]\n{tool_calls_str}"

        return f"{role_str} {content_str}"

    def format_enhanced_message(self, message: MessageProtocol) -> str:
        """Format an enhanced message with content objects.

        Args:
            message: The message to format

        Returns:
            Formatted message as a string
        """
        # Check if message has content_objects attribute
        if not hasattr(message, "content_objects"):
            return self.format_message(message)

        content_objects = getattr(message, "content_objects")
        if not content_objects:
            return self.format_message(message)

        # Extract role string in UPPERCASE with brackets, handling different role types
        try:
            if hasattr(message.role, "value"):
                # Handle enum Role.ASSISTANT case
                role_value = str(message.role.value).upper()
            elif isinstance(message.role, str):
                # Handle string case
                role_value = message.role.upper()
            else:
                # Last resort: convert to string and handle enum representation
                role_str = str(message.role).upper()
                if "." in role_str:
                    # Handle "Role.ASSISTANT" format
                    role_value = role_str.split(".")[-1].upper()
                else:
                    role_value = role_str
        except Exception:
            # Ultimate fallback
            role_value = "UNKNOWN"

        # Format role with brackets
        role_str = f"[{role_value}]"

        # Add name if present
        if message.name:
            role_str = f"{role_str} ({message.name})"

        # Format content objects
        content_parts = [self.format_content(content) for content in content_objects]
        content_str = "\n".join(filter(None, content_parts))

        # Return with base MessageFormatter style (space after role, no colon)
        return f"{role_str} {content_str}"

    def format_content(self, content: ContentProtocol) -> str:
        """Format a content object into a string representation.

        Args:
            content: The content object to format

        Returns:
            Formatted content as a string
        """
        # Default implementation uses to_string method
        return content.to_string()

    def format_messages(self, messages: List[MessageProtocol]) -> str:
        """Format multiple messages into a conversation.

        Args:
            messages: List of messages to format

        Returns:
            Formatted conversation as a string
        """
        formatted_messages = []

        for message in messages:
            if hasattr(message, "content_objects"):
                formatted_messages.append(self.format_enhanced_message(message))
            else:
                formatted_messages.append(self.format_message(message))

        return "\n\n".join(formatted_messages)


# -----------------------------------------------------------------------------
# Specialized Formatters
# -----------------------------------------------------------------------------


class PlainTextFormatter(MessageFormatter):
    """Format messages as plain text without markdown.

    This formatter strips formatting markers and presents messages
    in a simple, readable text format suitable for plain text environments.
    """

    def format_message(self, message: MessageProtocol) -> str:
        """Format message as plain text.

        Args:
            message: The message to format

        Returns:
            Formatted message as plain text
        """
        # Convert role to lowercase string
        role_value = (
            message.role.value.lower() if hasattr(message.role, "value") else message.role.lower()
        )

        if message.name:
            role_str = f"{role_value} ({message.name})"
        else:
            role_str = f"{role_value}"

        content_str = message.content or ""

        # Strip markdown and formatting
        content_str = self._strip_markdown(content_str)

        if message.base64_image:
            content_str += "\n[Image]"

        if message.tool_calls:
            content_str += (
                "\n[Tools: " + ", ".join([tc.function.name for tc in message.tool_calls]) + "]"
            )

        return f"{role_str}: {content_str}"

    def format_enhanced_message(self, message: MessageProtocol) -> str:
        """Format an enhanced message with content objects for plain text.

        Args:
            message: The message to format

        Returns:
            Formatted message as plain text
        """
        # Check if message has content_objects attribute
        if not hasattr(message, "content_objects"):
            return self.format_message(message)

        content_objects = getattr(message, "content_objects")
        if not content_objects:
            return self.format_message(message)

        # Extract role string in lowercase, handling different possible types
        try:
            if hasattr(message.role, "value"):
                # Handle enum Role.ASSISTANT case
                role_value = str(message.role.value).lower()
            elif isinstance(message.role, str):
                # Handle string case
                role_value = message.role.lower()
            else:
                # Last resort: convert to string and handle enum representation
                role_str = str(message.role).lower()
                if "." in role_str:
                    # Handle "Role.ASSISTANT" format
                    role_value = role_str.split(".")[-1].lower()
                else:
                    role_value = role_str
        except Exception:
            # Ultimate fallback
            role_value = "unknown"

        # Format name if present
        if message.name:
            role_str = f"{role_value} ({message.name})"
        else:
            role_str = f"{role_value}"

        # Format content objects
        content_parts = [self.format_content(content) for content in content_objects]
        content_str = "\n".join(filter(None, content_parts))

        # Return with PlainTextFormatter style (colon after role)
        return f"{role_str}: {content_str}"

    def format_content(self, content: ContentProtocol) -> str:
        """Format content object as plain text.

        Args:
            content: The content object to format

        Returns:
            Formatted content as plain text
        """
        content_type = content.get_content_type()

        if content_type == CONTENT_TYPE_TEXT:
            text_content = cast(TextContent, content)
            return text_content.text

        elif content_type == CONTENT_TYPE_CODE:
            code_content = cast(CodeContent, content)
            return f"[Code: {code_content.language}]\n{code_content.code}"

        elif content_type == CONTENT_TYPE_MARKDOWN:
            md_content = cast(MarkdownContent, content)
            return self._strip_markdown(md_content.markdown)

        elif content_type == CONTENT_TYPE_IMAGE:
            img_content = cast(ImageContent, content)
            if img_content.alt_text:
                return f"[Image: {img_content.alt_text}]"
            return "[Image]"

        elif content_type == CONTENT_TYPE_TOOL_CALL:
            tool_content = cast(ToolCallContent, content)
            tool_names = [tc.function.name for tc in tool_content.tool_calls]
            return f"[Tools: {', '.join(tool_names)}]"

        elif content_type == CONTENT_TYPE_FILE:
            file_content = cast(FileContent, content)
            return f"[File: {file_content.filename}]"

        else:
            return content.to_string()

    def _strip_markdown(self, text: str) -> str:
        """Strip markdown formatting from text.

        Args:
            text: Text with markdown formatting

        Returns:
            Plain text without markdown
        """
        if not text:
            return ""

        # Replace code blocks with just their content (preserve the code)
        text = re.sub(
            rf"{CODE_BLOCK_START}(\w*)\n(.*?){CODE_BLOCK_END}",
            lambda m: m.group(2),  # Keep only the code content
            text,
            flags=re.DOTALL,
        )

        # Remove inline code
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Remove bold and italic
        text = text.replace(BOLD_MARKER, "")
        text = text.replace(ITALIC_MARKER, "")

        # Remove strikethrough
        text = text.replace(STRIKETHROUGH_MARKER, "")

        # Remove headings
        text = re.sub(rf"^{HEADING_MARKER}+\s*", "", text, flags=re.MULTILINE)

        # Remove list markers
        text = re.sub(rf"^{UNORDERED_LIST_MARKER}", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)

        # Remove blockquotes
        text = re.sub(rf"^{BLOCKQUOTE_MARKER}", "", text, flags=re.MULTILINE)

        # Convert links to text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

        # Remove extra whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()


class MarkdownFormatter(MessageFormatter):
    """Format messages as markdown.

    This formatter enhances message formatting with markdown syntax,
    suitable for rendering in markdown-compatible environments.
    """

    def format_message(self, message: MessageProtocol) -> str:
        """Format message as markdown.

        Args:
            message: The message to format

        Returns:
            Formatted message in markdown
        """
        role_str = f"**{message.role.upper()}**"
        if message.name:
            role_str = f"{role_str} _{message.name}_"

        sections = []

        # Add content if present
        if message.content:
            sections.append(message.content)

        # Add image reference if present
        if message.base64_image:
            sections.append("![Image](data:image/png;base64,{truncated})")

        # Add tool calls in formatted markdown
        if message.tool_calls:
            for tc in message.tool_calls:
                sections.append(
                    f"**Function Call:** `{tc.function.name}`\n```json\n{tc.function.arguments}\n```"
                )

        content_str = "\n\n".join(sections)
        return f"{role_str}\n\n{content_str}"

    def format_content(self, content: ContentProtocol) -> str:
        """Format content object as markdown.

        Args:
            content: The content object to format

        Returns:
            Formatted content in markdown
        """
        content_type = content.get_content_type()

        if content_type == CONTENT_TYPE_TEXT:
            text_content = cast(TextContent, content)
            return text_content.text

        elif content_type == CONTENT_TYPE_CODE:
            code_content = cast(CodeContent, content)
            return f"```{code_content.language}\n{code_content.code}\n```"

        elif content_type == CONTENT_TYPE_MARKDOWN:
            md_content = cast(MarkdownContent, content)
            return md_content.markdown

        elif content_type == CONTENT_TYPE_IMAGE:
            img_content = cast(ImageContent, content)
            alt_text = img_content.alt_text or "Image"
            # For markdown we can't embed the actual image data efficiently
            return f"![{alt_text}](image data not shown)"

        elif content_type == CONTENT_TYPE_TOOL_CALL:
            tool_content = cast(ToolCallContent, content)
            tool_sections = []

            for tc in tool_content.tool_calls:
                tool_sections.append(
                    f"**Function Call:** `{tc.function.name}`\n```json\n{tc.function.arguments}\n```"
                )

            return "\n\n".join(tool_sections)

        elif content_type == CONTENT_TYPE_FILE:
            file_content = cast(FileContent, content)
            return f"**File:** {file_content.filename} ({file_content.mime_type})"

        else:
            return content.to_string()

    def format_messages(self, messages: List[MessageProtocol]) -> str:
        """Format multiple messages as a markdown conversation.

        Args:
            messages: List of messages to format

        Returns:
            Formatted conversation in markdown
        """
        formatted = []

        for i, message in enumerate(messages):
            if i > 0:
                formatted.append("---")  # Add separator between messages

            if hasattr(message, "content_objects"):
                formatted.append(self.format_enhanced_message(message))
            else:
                formatted.append(self.format_message(message))

        return "\n\n".join(formatted)


class HTMLFormatter(MessageFormatter):
    """Format messages as HTML.

    This formatter converts messages to HTML markup suitable
    for web display, including proper handling of images and code.
    """

    def format_message(self, message: MessageProtocol) -> str:
        """Format message as HTML.

        Args:
            message: The message to format

        Returns:
            Formatted message as HTML
        """
        role_class = f"message-{message.role.lower()}"
        role_text = message.role.upper()

        # Create HTML components
        html_parts = [f'<div class="message {role_class}">']
        html_parts.append('<div class="message-header">')
        html_parts.append(f'<span class="message-role">{role_text}</span>')

        if message.name:
            html_parts.append(f'<span class="message-name">{message.name}</span>')

        html_parts.append("</div>")
        html_parts.append('<div class="message-content">')

        # Add content if available
        if message.content:
            # Convert markdown to HTML
            html_content = self._markdown_to_html(message.content)
            html_parts.append(html_content)

        # Add image if available
        if message.base64_image:
            html_parts.append('<div class="message-image">')
            html_parts.append(
                f'<img src="data:image/png;base64,{message.base64_image}" alt="Image" />'
            )
            html_parts.append("</div>")

        # Add tool calls if available
        if message.tool_calls:
            html_parts.append('<div class="message-tool-calls">')
            html_parts.append("<h4>Function Calls</h4>")

            for tc in message.tool_calls:
                html_parts.append('<div class="tool-call">')
                html_parts.append(f'<div class="tool-call-name">{tc.function.name}</div>')
                html_parts.append('<pre class="tool-call-args">')
                html_parts.append(self._escape_html(tc.function.arguments))
                html_parts.append("</pre>")
                html_parts.append("</div>")

            html_parts.append("</div>")

        html_parts.append("</div>")  # Close message-content
        html_parts.append("</div>")  # Close message

        return "\n".join(html_parts)

    def format_enhanced_message(self, message: MessageProtocol) -> str:
        """Format an enhanced message with content objects as HTML.

        Args:
            message: The message to format

        Returns:
            Formatted message as HTML
        """
        # Check if message has content_objects attribute
        if not hasattr(message, "content_objects"):
            return self.format_message(message)

        content_objects = getattr(message, "content_objects")
        if not content_objects:
            return self.format_message(message)

        # Get role in lowercase for CSS class
        if hasattr(message.role, "value"):
            role_value = message.role.value.lower()
        elif isinstance(message.role, str):
            role_value = message.role.lower()
        else:
            # Handle any other case
            role_value = str(message.role).lower()
            if "." in role_value:
                role_value = role_value.split(".")[-1].lower()

        # Get role in uppercase for display
        if hasattr(message.role, "value"):
            role_text = message.role.value.upper()
        elif isinstance(message.role, str):
            role_text = message.role.upper()
        else:
            role_text = str(message.role).upper()
            if "." in role_text:
                role_text = role_text.split(".")[-1].upper()

        # Create HTML components
        role_class = f"message-{role_value}"
        html_parts = [f'<div class="message {role_class}">']
        html_parts.append('<div class="message-header">')
        html_parts.append(f'<span class="message-role">{role_text}</span>')

        if message.name:
            html_parts.append(f'<span class="message-name">{message.name}</span>')

        html_parts.append("</div>")
        html_parts.append('<div class="message-content">')

        # Format each content object and add to HTML
        for content_obj in content_objects:
            html_parts.append(self.format_content(content_obj))

        html_parts.append("</div>")  # Close message-content
        html_parts.append("</div>")  # Close message

        return "\n".join(html_parts)

    def format_content(self, content: ContentProtocol) -> str:
        """Format content object as HTML.

        Args:
            content: The content object to format

        Returns:
            Formatted content as HTML
        """
        content_type = content.get_content_type()

        if content_type == CONTENT_TYPE_TEXT:
            text_content = cast(TextContent, content)
            return f'<div class="content-text">{self._escape_html(text_content.text)}</div>'

        elif content_type == CONTENT_TYPE_CODE:
            code_content = cast(CodeContent, content)
            return (
                f'<div class="content-code">\n'
                f'<div class="code-language">{code_content.language}</div>\n'
                f'<pre><code class="language-{code_content.language}">{self._escape_html(code_content.code)}</code></pre>\n'
                f"</div>"
            )

        elif content_type == CONTENT_TYPE_MARKDOWN:
            md_content = cast(MarkdownContent, content)
            return (
                f'<div class="content-markdown">{self._markdown_to_html(md_content.markdown)}</div>'
            )

        elif content_type == CONTENT_TYPE_IMAGE:
            img_content = cast(ImageContent, content)
            alt_text = img_content.alt_text or "Image"

            # Handle different image data types
            if isinstance(img_content.data, str):
                img_src = f"data:image/{img_content.format};base64,{img_content.data}"
            else:
                # For bytes, we'd need to encode
                import base64

                encoded = base64.b64encode(img_content.data).decode("utf-8")
                img_src = f"data:image/{img_content.format};base64,{encoded}"

            return f'<div class="content-image"><img src="{img_src}" alt="{alt_text}" /></div>'

        elif content_type == CONTENT_TYPE_TOOL_CALL:
            tool_content = cast(ToolCallContent, content)
            html_parts = ['<div class="content-tool-calls">']

            for tc in tool_content.tool_calls:
                html_parts.append('<div class="tool-call">')
                html_parts.append(f'<div class="tool-call-name">{tc.function.name}</div>')
                html_parts.append('<pre class="tool-call-args">')
                html_parts.append(self._escape_html(tc.function.arguments))
                html_parts.append("</pre>")
                html_parts.append("</div>")

            html_parts.append("</div>")
            return "\n".join(html_parts)

        elif content_type == CONTENT_TYPE_FILE:
            file_content = cast(FileContent, content)
            return (
                f'<div class="content-file">'
                f'<div class="file-info">{file_content.filename} ({file_content.mime_type})</div>'
                f"</div>"
            )

        else:
            return f'<div class="content-unknown">{self._escape_html(content.to_string())}</div>'

    def format_messages(self, messages: List[MessageProtocol]) -> str:
        """Format multiple messages as an HTML conversation.

        Args:
            messages: List of messages to format

        Returns:
            Formatted conversation as HTML
        """
        html_parts = ['<div class="conversation">']

        for message in messages:
            if hasattr(message, "content_objects"):
                html_parts.append(self.format_enhanced_message(message))
            else:
                html_parts.append(self.format_message(message))

        html_parts.append("</div>")

        return "\n".join(html_parts)

    def get_full_html_document(
        self, messages: List[MessageProtocol], title: str = "Conversation"
    ) -> str:
        """Generate a complete HTML document with conversation.

        Args:
            messages: List of messages to format
            title: Document title

        Returns:
            Complete HTML document
        """
        css = """
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
            .conversation { border: 1px solid #eee; border-radius: 8px; overflow: hidden; }
            .message { padding: 15px; border-bottom: 1px solid #eee; }
            .message:last-child { border-bottom: none; }
            .message-user { background-color: #f5f8ff; }
            .message-assistant { background-color: #f9f9f9; }
            .message-system { background-color: #fffbf0; border-left: 3px solid #ffcc00; }
            .message-tool { background-color: #f0f8ff; border-left: 3px solid #66aaff; }
            .message-agent { background-color: #f0fff8; border-left: 3px solid #00cc88; }
            .message-header { margin-bottom: 10px; font-weight: bold; }
            .message-role { display: inline-block; background: #555; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; }
            .message-name { margin-left: 8px; color: #666; font-style: italic; }
            .content-code { background: #f4f4f4; border-radius: 4px; padding: 1px; margin: 10px 0; }
            .code-language { color: #666; font-size: 0.8em; padding: 4px 10px; border-bottom: 1px solid #ddd; }
            pre { margin: 0; padding: 10px; overflow-x: auto; }
            code { font-family: monospace; }
            .content-image { margin: 10px 0; }
            .content-image img { max-width: 100%; border-radius: 4px; }
            .tool-call { border: 1px solid #ddd; border-radius: 4px; margin: 10px 0; }
            .tool-call-name { background: #f0f0f0; padding: 5px 10px; border-bottom: 1px solid #ddd; font-weight: bold; }
            .tool-call-args { margin: 0; padding: 10px; white-space: pre-wrap; }
        </style>
        """

        html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            {css}
        </head>
        <body>
            <h1>{title}</h1>
            {self.format_messages(messages)}
        </body>
        </html>
        """

        return html

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters.

        Args:
            text: Text to escape

        Returns:
            HTML-escaped text
        """
        if not text:
            return ""

        from enterprise_ai.message.constants import HTML_SPECIAL_CHARS

        for char, entity in HTML_SPECIAL_CHARS.items():
            text = text.replace(char, entity)

        return text

    def _markdown_to_html(self, markdown: str) -> str:
        """Convert markdown to HTML.

        Args:
            markdown: Markdown text

        Returns:
            HTML representation
        """
        if not markdown:
            return ""

        # This is a simplified markdown to HTML converter
        # In a real implementation, you might use a library like markdown

        html = markdown

        # Convert headings
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)

        # Convert code blocks
        html = re.sub(
            r"```(\w*)\n(.*?)\n```",
            lambda m: f'<pre><code class="language-{m.group(1) or "text"}">{self._escape_html(m.group(2))}</code></pre>',
            html,
            flags=re.DOTALL,
        )

        # Convert inline code
        html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

        # Convert bold and italic
        html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", html)

        # Convert lists
        html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        # Wrap lists with <ul>
        html = re.sub(r"(<li>.*</li>)", r"<ul>\1</ul>", html, flags=re.DOTALL)

        # Convert links
        html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)

        # Convert paragraphs
        html = re.sub(r"^\s*$", "</p><p>", html, flags=re.MULTILINE)
        html = f"<p>{html}</p>"
        html = html.replace("<p></p>", "")

        return html


class ConsoleFormatter(MessageFormatter):
    """Format messages for console output with ANSI colors.

    This formatter enhances messages with ANSI color codes for
    readable display in terminal environments.
    """

    # ANSI color codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    def __init__(self, use_colors: bool = True):
        """Initialize console formatter.

        Args:
            use_colors: Whether to use ANSI color codes (disable for non-supporting terminals)
        """
        self.use_colors = use_colors

    def format_message(self, message: MessageProtocol) -> str:
        """Format message for console output.

        Args:
            message: The message to format

        Returns:
            Formatted message with console colors
        """
        # Define colors by role
        role_colors = {
            "user": self.GREEN,
            "assistant": self.BLUE,
            "system": self.YELLOW,
            "tool": self.MAGENTA,
            "agent": self.CYAN,
        }

        # Convert role to string for consistency
        role_value = (
            message.role.value.lower() if hasattr(message.role, "value") else message.role.lower()
        )
        role_str = (
            message.role.upper() if isinstance(message.role, str) else message.role.value.upper()
        )

        # Get role color with fallback to default
        role_color = role_colors.get(role_value, self.WHITE)

        if self.use_colors:
            role_formatted = f"{role_color}{self.BOLD}[{role_str}]{self.RESET}"
        else:
            role_formatted = f"[{role_str}]"

        # Format name if present
        name_str = ""
        if message.name:
            if self.use_colors:
                name_str = f" {self.DIM}({message.name}){self.RESET}"
            else:
                name_str = f" ({message.name})"

        # Format content
        content_str = message.content or ""

        # Format image indicator
        image_str = ""
        if message.base64_image:
            if self.use_colors:
                image_str = f"\n{self.ITALIC}[Image included]{self.RESET}"
            else:
                image_str = "\n[Image included]"

        # Format tool calls
        tool_str = ""
        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                if self.use_colors:
                    tool_calls.append(
                        f"{self.BOLD}Function:{self.RESET} {tc.function.name}\n"
                        f"{self.BOLD}Arguments:{self.RESET} {tc.function.arguments}"
                    )
                else:
                    tool_calls.append(
                        f"Function: {tc.function.name}\nArguments: {tc.function.arguments}"
                    )

            tool_header = (
                f"\n{self.BOLD}[Tool Calls]{self.RESET}\n"
                if self.use_colors
                else "\n[Tool Calls]\n"
            )
            tool_str = tool_header + "\n\n".join(tool_calls)

        return f"{role_formatted}{name_str} {content_str}{image_str}{tool_str}"

    def format_content(self, content: ContentProtocol) -> str:
        """Format content object for console output.

        Args:
            content: The content object to format

        Returns:
            Formatted content with console colors
        """
        content_type = content.get_content_type()

        if content_type == CONTENT_TYPE_TEXT:
            text_content = cast(TextContent, content)
            return text_content.text

        elif content_type == CONTENT_TYPE_CODE:
            code_content = cast(CodeContent, content)

            if self.use_colors:
                lang_header = f"{self.YELLOW}{self.BOLD}[{code_content.language}]{self.RESET}\n"
                return f"{lang_header}{code_content.code}"
            else:
                return f"[{code_content.language}]\n{code_content.code}"

        elif content_type == CONTENT_TYPE_MARKDOWN:
            md_content = cast(MarkdownContent, content)
            # For console output, we could implement simple markdown formatting with colors
            # Here we just return the raw markdown
            return md_content.markdown

        elif content_type == CONTENT_TYPE_IMAGE:
            img_content = cast(ImageContent, content)
            alt_text = img_content.alt_text or "Image"

            if self.use_colors:
                return f"{self.ITALIC}[Image: {alt_text}]{self.RESET}"
            else:
                return f"[Image: {alt_text}]"

        elif content_type == CONTENT_TYPE_TOOL_CALL:
            tool_content = cast(ToolCallContent, content)
            tool_calls = []

            for tc in tool_content.tool_calls:
                if self.use_colors:
                    tool_calls.append(
                        f"{self.BOLD}Function:{self.RESET} {tc.function.name}\n"
                        f"{self.BOLD}Arguments:{self.RESET} {tc.function.arguments}"
                    )
                else:
                    tool_calls.append(
                        f"Function: {tc.function.name}\nArguments: {tc.function.arguments}"
                    )

            tool_header = (
                f"{self.BOLD}[Tool Calls]{self.RESET}\n" if self.use_colors else "[Tool Calls]\n"
            )
            return tool_header + "\n\n".join(tool_calls)

        elif content_type == CONTENT_TYPE_FILE:
            file_content = cast(FileContent, content)

            if self.use_colors:
                return f"{self.BOLD}[File: {file_content.filename} ({file_content.mime_type})]{self.RESET}"
            else:
                return f"[File: {file_content.filename} ({file_content.mime_type})]"

        else:
            return content.to_string()


# -----------------------------------------------------------------------------
# Formatter Registry
# -----------------------------------------------------------------------------


class FormatterRegistry:
    """Registry for message formatters.

    This class maintains a mapping of format identifiers to formatter instances
    and provides methods to register and retrieve formatters.
    """

    _formatters = {
        "default": MessageFormatter(),
        "plain": PlainTextFormatter(),
        "markdown": MarkdownFormatter(),
        "html": HTMLFormatter(),
        "console": ConsoleFormatter(),
    }

    @classmethod
    def register_formatter(cls, name: str, formatter: MessageFormatter) -> None:
        """Register a formatter with the given name.

        Args:
            name: Name to register the formatter under
            formatter: Formatter instance
        """
        cls._formatters[name] = formatter
        logger.info(f"Registered formatter: {name}")

    @classmethod
    def get_formatter(cls, name: str = "default") -> MessageFormatter:
        """Get a formatter by name.

        Args:
            name: Name of the formatter to retrieve

        Returns:
            Formatter instance
        """
        if name not in cls._formatters:
            logger.warning(f"Formatter '{name}' not found, using default")
            return cls._formatters["default"]

        return cls._formatters[name]

    @classmethod
    def format_message(cls, message: MessageProtocol, format_name: str = "default") -> str:
        """Format a message using the specified formatter.

        Args:
            message: Message to format
            format_name: Name of the formatter to use

        Returns:
            Formatted message
        """
        formatter = cls.get_formatter(format_name)

        if hasattr(message, "content_objects"):
            return formatter.format_enhanced_message(message)
        else:
            return formatter.format_message(message)

    @classmethod
    def format_messages(cls, messages: List[MessageProtocol], format_name: str = "default") -> str:
        """Format multiple messages using the specified formatter.

        Args:
            messages: Messages to format
            format_name: Name of the formatter to use

        Returns:
            Formatted messages
        """
        formatter = cls.get_formatter(format_name)
        return formatter.format_messages(messages)


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def format_message(message: MessageProtocol, format_name: str = "default") -> str:
    """Format a message using the specified format.

    Args:
        message: Message to format
        format_name: Format to use

    Returns:
        Formatted message
    """
    return FormatterRegistry.format_message(message, format_name)


def format_messages(messages: List[MessageProtocol], format_name: str = "default") -> str:
    """Format multiple messages using the specified format.

    Args:
        messages: Messages to format
        format_name: Format to use

    Returns:
        Formatted messages
    """
    return FormatterRegistry.format_messages(messages, format_name)


def get_formatter(name: str) -> MessageFormatter:
    """Get a formatter by name.

    Args:
        name: Name of the formatter

    Returns:
        Formatter instance
    """
    return FormatterRegistry.get_formatter(name)


def register_formatter(name: str, formatter: MessageFormatter) -> None:
    """Register a custom formatter.

    Args:
        name: Name to register the formatter under
        formatter: Formatter instance
    """
    FormatterRegistry.register_formatter(name, formatter)


def message_to_html(message: MessageProtocol) -> str:
    """Convert a message to HTML.

    Args:
        message: Message to convert

    Returns:
        HTML representation
    """
    return format_message(message, "html")


def message_to_markdown(message: MessageProtocol) -> str:
    """Convert a message to markdown.

    Args:
        message: Message to convert

    Returns:
        Markdown representation
    """
    return format_message(message, "markdown")


def conversation_to_html(messages: List[MessageProtocol], title: str = "Conversation") -> str:
    """Convert a conversation to a complete HTML document.

    Args:
        messages: Messages in the conversation
        title: Document title

    Returns:
        Complete HTML document
    """
    formatter = FormatterRegistry.get_formatter("html")
    if isinstance(formatter, HTMLFormatter):
        return formatter.get_full_html_document(messages, title)

    # Fallback if not an HTMLFormatter
    html_formatter = HTMLFormatter()
    return html_formatter.get_full_html_document(messages, title)
