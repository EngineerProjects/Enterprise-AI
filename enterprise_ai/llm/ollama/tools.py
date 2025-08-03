"""
FIXED: Tool handling for Ollama provider using shared utilities.

MAJOR REFACTOR: Eliminated 400+ lines of duplicate code by leveraging
shared tool conversion utilities from enterprise_ai.schema.tool_utils.
"""

import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolDefinition
from enterprise_ai.schema.tool_utils import ToolConverter  # Use shared utility
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.ollama.tools")


class OllamaToolConverter:
    """REFACTORED: Ollama tool converter using shared utilities for consistency."""

    @staticmethod
    def normalize_tools(tools: Sequence[Union[Dict[str, Any], Callable, ToolDefinition]]) -> List[Dict[str, Any]]:
        """Normalize tools to Ollama format using shared conversion logic."""
        normalized = []
        
        for i, tool in enumerate(tools):
            try:
                if isinstance(tool, ToolDefinition):
                    # Use shared schema - just convert to Ollama format
                    ollama_tool = OllamaToolConverter._tool_definition_to_ollama_format(tool)
                    normalized.append(ollama_tool)
                elif callable(tool):
                    # FIXED: Use shared conversion logic instead of reimplementing
                    tool_def = ToolConverter.function_to_tool_definition(tool)
                    ollama_tool = OllamaToolConverter._tool_definition_to_ollama_format(tool_def)
                    normalized.append(ollama_tool)
                elif isinstance(tool, dict):
                    # FIXED: Use shared schema validation then convert
                    if OllamaToolConverter._is_ollama_format(tool):
                        normalized.append(tool)
                    else:
                        tool_def = ToolDefinition.from_dict(tool)
                        ollama_tool = OllamaToolConverter._tool_definition_to_ollama_format(tool_def)
                        normalized.append(ollama_tool)
                else:
                    raise ValueError(f"Unsupported tool format: {type(tool)}")
            except Exception as e:
                logger.error(f"Failed to normalize tool {i} ({type(tool)}): {e}")
                continue
        
        return normalized

    @staticmethod
    def _tool_definition_to_ollama_format(tool_def: ToolDefinition) -> Dict[str, Any]:
        """Convert ToolDefinition to Ollama API specification format."""
        ollama_tool = {
            "type": "function",
            "function": {
                "name": tool_def.get_name(),
                "description": tool_def.get_description() or "",
                "parameters": tool_def.get_parameters() or {}
            }
        }
        
        # Ensure parameters have proper JSON schema structure
        if not isinstance(ollama_tool["function"]["parameters"], dict):
            ollama_tool["function"]["parameters"] = {}
        
        if "type" not in ollama_tool["function"]["parameters"]:
            ollama_tool["function"]["parameters"]["type"] = "object"
        
        if "properties" not in ollama_tool["function"]["parameters"]:
            ollama_tool["function"]["parameters"]["properties"] = {}
        
        return ollama_tool

    @staticmethod
    def _is_ollama_format(tool: Dict[str, Any]) -> bool:
        """Check if tool is already in Ollama format."""
        return (
            tool.get("type") == "function" and
            "function" in tool and
            isinstance(tool["function"], dict) and
            "name" in tool["function"]
        )


class OllamaToolExtractor:
    """Enhanced tool extractor with pattern matching for Ollama-specific formats."""

    def __init__(self):
        # Enhanced patterns for Ollama tool call extraction
        self._patterns = {
            "tool_call_tags": re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL | re.IGNORECASE),
            "ollama_calls": re.compile(r"<function_calls>\s*(.*?)\s*</function_calls>", re.DOTALL | re.IGNORECASE),
            "json_blocks": re.compile(r"```(?:json)?\s*({[\s\S]*?})```", re.DOTALL),
            "direct_json": re.compile(r'{"(?:function|tool|name)"\s*:\s*"[^"]+"\s*,[\s\S]*?}', re.DOTALL),
        }

    def extract_tool_calls_to_schema(self, content: str) -> List[ToolCall]:
        """Extract tool calls using prioritized extraction strategies."""
        if not content:
            return []
        
        extraction_strategies = [
            ("tool_call_tags", self._extract_from_tool_call_tags),
            ("ollama_calls", self._extract_from_ollama_calls),
            ("json_blocks", self._extract_from_json_blocks),
            ("direct_json", self._extract_from_direct_json),
        ]
        
        for strategy_name, extract_func in extraction_strategies:
            try:
                found_calls = extract_func(content)
                if found_calls:
                    return self._validate_tool_calls(found_calls)
            except Exception as e:
                logger.debug(f"Strategy {strategy_name} failed: {e}")
        
        return []

    def _extract_from_tool_call_tags(self, content: str) -> List[ToolCall]:
        """Extract from <tool_call> tags (granite3.2-vision format)."""
        tool_calls = []
        for match in self._patterns["tool_call_tags"].finditer(content):
            calls_content = match.group(1).strip()
            tool_calls.extend(self._parse_json_content(calls_content))
        return tool_calls

    def _extract_from_ollama_calls(self, content: str) -> List[ToolCall]:
        """Extract from Ollama-style function_calls blocks."""
        tool_calls = []
        for match in self._patterns["ollama_calls"].finditer(content):
            calls_content = match.group(1).strip()
            tool_calls.extend(self._parse_json_content(calls_content))
        return tool_calls

    def _extract_from_json_blocks(self, content: str) -> List[ToolCall]:
        """Extract from JSON code blocks."""
        tool_calls = []
        for match in self._patterns["json_blocks"].finditer(content):
            json_str = match.group(1).strip()
            try:
                json_data = json.loads(json_str)
                if isinstance(json_data, list):
                    for item in json_data:
                        tool_call = self._json_to_tool_call_schema(item)
                        if tool_call:
                            tool_calls.append(tool_call)
                else:
                    tool_call = self._json_to_tool_call_schema(json_data)
                    if tool_call:
                        tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue
        return tool_calls

    def _extract_from_direct_json(self, content: str) -> List[ToolCall]:
        """Extract from direct JSON tool calls in text."""
        tool_calls = []
        for match in self._patterns["direct_json"].finditer(content):
            try:
                json_data = json.loads(match.group(0))
                tool_call = self._json_to_tool_call_schema(json_data)
                if tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue
        return tool_calls

    def _parse_json_content(self, content: str) -> List[ToolCall]:
        """Parse JSON content that might be array or single object."""
        tool_calls = []
        try:
            data = json.loads(content)
            if isinstance(data, list):
                for item in data:
                    tool_call = self._json_to_tool_call_schema(item)
                    if tool_call:
                        tool_calls.append(tool_call)
            else:
                tool_call = self._json_to_tool_call_schema(data)
                if tool_call:
                    tool_calls.append(tool_call)
        except json.JSONDecodeError:
            # Try line by line parsing
            for line in content.split('\n'):
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        tool_call = self._json_to_tool_call_schema(data)
                        if tool_call:
                            tool_calls.append(tool_call)
                    except json.JSONDecodeError:
                        continue
        return tool_calls

    def _json_to_tool_call_schema(self, json_data: Dict[str, Any]) -> Optional[ToolCall]:
        """Convert JSON to ToolCall schema with enhanced field extraction."""
        if not isinstance(json_data, dict):
            return None
        
        # Extract tool name with multiple field options
        tool_name = None
        for name_field in ["name", "tool", "function_name", "function"]:
            if name_field in json_data:
                if name_field == "function" and isinstance(json_data[name_field], dict):
                    tool_name = json_data[name_field].get("name")
                else:
                    tool_name = json_data[name_field]
                break
        
        if not tool_name:
            return None
        
        # Extract parameters/arguments
        params = {}
        for param_field in ["arguments", "parameters", "args", "params"]:
            if param_field in json_data:
                params = json_data[param_field]
                break
        
        # Handle Ollama function format
        if "function" in json_data and isinstance(json_data["function"], dict):
            func_data = json_data["function"]
            params = func_data.get("arguments", func_data.get("parameters", {}))
        
        # Ensure params is a dict
        if not isinstance(params, dict):
            params = {"value": params}
        
        # Generate unique ID
        call_id = json_data.get("id", f"extracted_{int(time.time() * 1000000)}_{hash(tool_name) % 10000}")
        
        return ToolCall.create(name=tool_name, arguments=params, id=call_id)

    def _validate_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolCall]:
        """Validate extracted tool calls."""
        return [tc for tc in tool_calls if tc.function.name and tc.function.arguments is not None]

    def extract_native_tool_calls(self, response_data: Dict[str, Any]) -> List[ToolCall]:
        """Extract native tool calls from Ollama response format."""
        tool_calls = []
        message = response_data.get("message", {})
        
        if "tool_calls" in message:
            for raw_tc in message["tool_calls"]:
                try:
                    if "function" in raw_tc:
                        func_data = raw_tc["function"]
                        tool_call = ToolCall.create(
                            name=func_data.get("name", ""),
                            arguments=func_data.get("arguments", {}),
                            id=raw_tc.get("id", f"native_{int(time.time() * 1000000)}_{len(tool_calls)}")
                        )
                        tool_calls.append(tool_call)
                    else:
                        tool_call = ToolCall.from_dict(raw_tc)
                        tool_calls.append(tool_call)
                except Exception as e:
                    logger.debug(f"Failed to parse native tool call: {e}")
        
        return tool_calls

    # Backward compatibility method
    def extract_tool_calls(self, message: MessageProtocol) -> List[Dict[str, Any]]:
        """Backward compatibility method returning dict format."""
        schema_calls = self.extract_tool_calls_to_schema(message.content or "")
        return [tc.to_dict() for tc in schema_calls]
