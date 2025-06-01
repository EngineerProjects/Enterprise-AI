"""
Tool handling for Ollama provider using schema classes.
Simplified to use shared utilities and maintain original functionality.
"""

import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolDefinition
from enterprise_ai.schema.tool_utils import ToolConverter  # Shared utility
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.ollama.tools")


class OllamaToolConverter:
    """Ollama tool converter using shared utilities."""

    @staticmethod
    def normalize_tools(tools: Sequence[Union[Dict[str, Any], Callable, ToolDefinition]]) -> List[Dict[str, Any]]:
        """Normalize tools using shared conversion logic."""
        normalized = []
        
        for tool in tools:
            try:
                if isinstance(tool, ToolDefinition):
                    normalized.append(tool.to_dict())
                elif callable(tool):
                    # Use shared conversion logic
                    tool_def = ToolConverter.function_to_tool_definition(tool)
                    normalized.append(tool_def.to_dict())
                elif isinstance(tool, dict):
                    tool_def = ToolDefinition.from_dict(tool)
                    normalized.append(tool_def.to_dict())
                else:
                    raise ValueError(f"Unsupported tool format: {type(tool)}")
            except Exception as e:
                logger.error(f"Failed to normalize tool: {e}")
        
        return normalized


class OllamaToolExtractor:
    """Tool extractor using schema classes (original logic preserved)."""

    def __init__(self):
        self._patterns = {
            "json_blocks": re.compile(r"```(?:json)?\s*({[\s\S]*?})```", re.DOTALL),
            "function_calls": re.compile(r"(\w+)\s*\(\s*({[^}]*})\s*\)", re.DOTALL),
            "tool_tags": re.compile(r"<tool[^>]*name=[\"']([^\"']+)[\"'][^>]*>(.*?)</tool>", re.DOTALL | re.IGNORECASE),
        }

    def extract_tool_calls_to_schema(self, content: str) -> List[ToolCall]:
        """Extract tool calls returning schema objects."""
        if not content:
            return []
        
        tool_calls = []
        
        for strategy_name, extract_func in [
            ("json_blocks", self._extract_from_json_blocks),
            ("function_calls", self._extract_from_function_calls),
            ("tool_tags", self._extract_from_tool_tags),
        ]:
            try:
                found_calls = extract_func(content)
                tool_calls.extend(found_calls)
                if found_calls:
                    logger.debug(f"Extracted {len(found_calls)} tool calls using {strategy_name}")
            except Exception as e:
                logger.debug(f"Strategy {strategy_name} failed: {e}")
        
        return tool_calls

    def _extract_from_json_blocks(self, content: str) -> List[ToolCall]:
        """Extract from JSON code blocks."""
        tool_calls = []
        for match in self._patterns["json_blocks"].finditer(content):
            try:
                json_data = json.loads(match.group(1))
                tool_call = self._json_to_tool_call_schema(json_data)
                if tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue
        return tool_calls

    def _extract_from_function_calls(self, content: str) -> List[ToolCall]:
        """Extract from function call patterns."""
        tool_calls = []
        for match in self._patterns["function_calls"].finditer(content):
            try:
                function_name = match.group(1)
                args_json = match.group(2)
                args = json.loads(args_json)
                
                tool_call = ToolCall.create(
                    name=function_name,
                    arguments=args,
                    id=f"func_{int(time.time() * 1000)}"
                )
                tool_calls.append(tool_call)
            except (json.JSONDecodeError, Exception):
                continue
        return tool_calls

    def _extract_from_tool_tags(self, content: str) -> List[ToolCall]:
        """Extract from XML tool tags."""
        tool_calls = []
        for match in self._patterns["tool_tags"].finditer(content):
            try:
                tool_name = match.group(1)
                tool_content = match.group(2).strip()
                
                try:
                    args = json.loads(tool_content)
                except json.JSONDecodeError:
                    args = {"content": tool_content}
                
                tool_call = ToolCall.create(
                    name=tool_name,
                    arguments=args,
                    id=f"tag_{int(time.time() * 1000)}"
                )
                tool_calls.append(tool_call)
            except Exception:
                continue
        return tool_calls

    def _json_to_tool_call_schema(self, json_data: Dict[str, Any]) -> Optional[ToolCall]:
        """Convert JSON to ToolCall schema."""
        if not isinstance(json_data, dict):
            return None
        
        # Extract tool name
        tool_name = (
            json_data.get("tool") or 
            json_data.get("name") or 
            json_data.get("function_name")
        )
        
        if "function" in json_data and isinstance(json_data["function"], dict):
            tool_name = json_data["function"].get("name")
        
        if not tool_name:
            return None
        
        # Extract parameters
        params = (
            json_data.get("parameters") or 
            json_data.get("arguments") or 
            json_data.get("args") or 
            {}
        )
        
        if "function" in json_data and isinstance(json_data["function"], dict):
            params = json_data["function"].get("arguments", {})
        
        return ToolCall.create(
            name=tool_name,
            arguments=params,
            id=json_data.get("id", f"json_{int(time.time() * 1000)}")
        )

    # Backward compatibility
    def extract_tool_calls(self, message: MessageProtocol) -> List[Dict[str, Any]]:
        """Backward compatibility method."""
        schema_calls = self.extract_tool_calls_to_schema(message.content or "")
        return [tc.to_dict() for tc in schema_calls]