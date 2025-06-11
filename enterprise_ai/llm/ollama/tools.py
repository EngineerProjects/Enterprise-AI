"""
FIXED: Tool handling for Ollama provider with full API specification compliance.

Key compliance fixes:
1. Tool format validation against Ollama specification
2. Enhanced tool call extraction for both native and content-based calls
3. Proper function schema conversion
4. Support for Ollama's tool calling format
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
    """FIXED: Ollama tool converter with API specification compliance."""

    @staticmethod
    def normalize_tools(tools: Sequence[Union[Dict[str, Any], Callable, ToolDefinition]]) -> List[Dict[str, Any]]:
        """FIXED: Normalize tools to Ollama API specification format."""
        normalized = []
        
        for i, tool in enumerate(tools):
            try:
                if isinstance(tool, ToolDefinition):
                    # Convert ToolDefinition to Ollama format
                    ollama_tool = OllamaToolConverter._tool_definition_to_ollama_format(tool)
                    normalized.append(ollama_tool)
                elif callable(tool):
                    # Convert function to ToolDefinition then to Ollama format
                    logger.debug(f"Converting function {tool.__name__} to ToolDefinition")
                    tool_def = ToolConverter.function_to_tool_definition(tool)
                    ollama_tool = OllamaToolConverter._tool_definition_to_ollama_format(tool_def)
                    normalized.append(ollama_tool)
                elif isinstance(tool, dict):
                    # Validate and convert dictionary to Ollama format
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
                # Continue with other tools instead of failing completely
                continue
        
        if normalized:
            return normalized

    @staticmethod
    def _tool_definition_to_ollama_format(tool_def: ToolDefinition) -> Dict[str, Any]:
        """FIXED: Convert ToolDefinition to Ollama API specification format."""
        # Ollama expects tools in this format according to the documentation
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
        
        # Add type if not present (required by JSON schema)
        if "type" not in ollama_tool["function"]["parameters"]:
            ollama_tool["function"]["parameters"]["type"] = "object"
        
        # Ensure properties exist
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

    @staticmethod
    def validate_ollama_tool_format(tool: Dict[str, Any]) -> bool:
        """FIXED: Validate tool against Ollama API specification."""
        try:
            # Check top level structure
            if not isinstance(tool, dict):
                return False
            
            if tool.get("type") != "function":
                return False
            
            function = tool.get("function")
            if not isinstance(function, dict):
                return False
            
            # Check required function fields
            if not function.get("name"):
                return False
            
            # Validate parameters structure (should be JSON schema)
            parameters = function.get("parameters", {})
            if not isinstance(parameters, dict):
                return False
            
            # If parameters exist, they should follow JSON schema
            if parameters:
                if "type" not in parameters:
                    return False
                if parameters["type"] != "object":
                    return False
                if "properties" not in parameters:
                    return False
                if not isinstance(parameters["properties"], dict):
                    return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Tool validation failed: {e}")
            return False


class OllamaToolExtractor:
    """FIXED: Tool extractor with enhanced pattern matching and Ollama compliance."""

    def __init__(self):
        # Enhanced patterns for better tool call extraction
        self._patterns = {
            # JSON blocks with optional language specifier
            "json_blocks": re.compile(r"```(?:json)?\s*({[\s\S]*?})```", re.DOTALL),
            # Function call patterns with flexible formatting
            "function_calls": re.compile(r"(\w+)\s*\(\s*({[^}]*}|\{[\s\S]*?\})\s*\)", re.DOTALL),
            # Tool tags (XML-style)
            "tool_tags": re.compile(r"<tool[^>]*name=[\"']([^\"']+)[\"'][^>]*>(.*?)</tool>", re.DOTALL | re.IGNORECASE),
            # Function calling format (Ollama style)
            "ollama_calls": re.compile(r"<function_calls>\s*(.*?)\s*</function_calls>", re.DOTALL | re.IGNORECASE),
            # Direct JSON tool calls
            "direct_json": re.compile(r'{"(?:function|tool|name)"\s*:\s*"[^"]+"\s*,[\s\S]*?}', re.DOTALL),
        }

    def extract_tool_calls_to_schema(self, content: str) -> List[ToolCall]:
        """FIXED: Extract tool calls with enhanced pattern matching and validation."""
        if not content:
            return []
        
        tool_calls = []
        extraction_strategies = [
            ("ollama_calls", self._extract_from_ollama_calls),
            ("json_blocks", self._extract_from_json_blocks),
            ("direct_json", self._extract_from_direct_json),
            ("function_calls", self._extract_from_function_calls),
            ("tool_tags", self._extract_from_tool_tags),
        ]
        
        for strategy_name, extract_func in extraction_strategies:
            try:
                found_calls = extract_func(content)
                if found_calls:
                    tool_calls.extend(found_calls)
                    # Stop after first successful extraction to avoid duplicates
                    break
            except Exception as e:
                pass
        
        # Validate extracted tool calls
        validated_calls = []
        for tc in tool_calls:
            if tc.name and tc.arguments is not None:
                validated_calls.append(tc)
        
        return validated_calls

    def _extract_from_ollama_calls(self, content: str) -> List[ToolCall]:
        """FIXED: Extract from Ollama-style function_calls blocks."""
        tool_calls = []
        for match in self._patterns["ollama_calls"].finditer(content):
            try:
                calls_content = match.group(1).strip()
                # Try to parse as JSON array or single object
                try:
                    calls_data = json.loads(calls_content)
                    if isinstance(calls_data, list):
                        for call_data in calls_data:
                            tool_call = self._json_to_tool_call_schema(call_data)
                            if tool_call:
                                tool_calls.append(tool_call)
                    else:
                        tool_call = self._json_to_tool_call_schema(calls_data)
                        if tool_call:
                            tool_calls.append(tool_call)
                except json.JSONDecodeError:
                    # Try line by line
                    for line in calls_content.split('\n'):
                        line = line.strip()
                        if line:
                            try:
                                call_data = json.loads(line)
                                tool_call = self._json_to_tool_call_schema(call_data)
                                if tool_call:
                                    tool_calls.append(tool_call)
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                pass
        return tool_calls

    def _extract_from_json_blocks(self, content: str) -> List[ToolCall]:
        """FIXED: Extract from JSON code blocks with better parsing."""
        tool_calls = []
        for match in self._patterns["json_blocks"].finditer(content):
            try:
                json_str = match.group(1).strip()
                json_data = json.loads(json_str)
                
                # Handle both single objects and arrays
                if isinstance(json_data, list):
                    for item in json_data:
                        tool_call = self._json_to_tool_call_schema(item)
                        if tool_call:
                            tool_calls.append(tool_call)
                else:
                    tool_call = self._json_to_tool_call_schema(json_data)
                    if tool_call:
                        tool_calls.append(tool_call)
            except json.JSONDecodeError as e:
                continue
        return tool_calls

    def _extract_from_direct_json(self, content: str) -> List[ToolCall]:
        """FIXED: Extract from direct JSON tool calls in text."""
        tool_calls = []
        for match in self._patterns["direct_json"].finditer(content):
            try:
                json_str = match.group(0)
                json_data = json.loads(json_str)
                tool_call = self._json_to_tool_call_schema(json_data)
                if tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue
        return tool_calls

    def _extract_from_function_calls(self, content: str) -> List[ToolCall]:
        """FIXED: Extract from function call patterns with better argument parsing."""
        tool_calls = []
        for match in self._patterns["function_calls"].finditer(content):
            try:
                function_name = match.group(1)
                args_str = match.group(2)
                
                # Try to parse arguments as JSON
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    # Try to fix common JSON issues
                    args_str = args_str.replace("'", '"')  # Single to double quotes
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {"content": args_str}  # Fallback
                
                tool_call = ToolCall.create(
                    name=function_name,
                    arguments=args,
                    id=f"func_{int(time.time() * 1000000)}_{len(tool_calls)}"
                )
                tool_calls.append(tool_call)
            except Exception as e:
                continue
        return tool_calls

    def _extract_from_tool_tags(self, content: str) -> List[ToolCall]:
        """FIXED: Extract from XML tool tags with better content parsing."""
        tool_calls = []
        for match in self._patterns["tool_tags"].finditer(content):
            try:
                tool_name = match.group(1)
                tool_content = match.group(2).strip()
                
                # Try to parse content as JSON
                try:
                    args = json.loads(tool_content)
                except json.JSONDecodeError:
                    # If not JSON, treat as text content
                    args = {"content": tool_content}
                
                tool_call = ToolCall.create(
                    name=tool_name,
                    arguments=args,
                    id=f"tag_{int(time.time() * 1000000)}_{len(tool_calls)}"
                )
                tool_calls.append(tool_call)
            except Exception as e:
                continue
        return tool_calls

    def _json_to_tool_call_schema(self, json_data: Dict[str, Any]) -> Optional[ToolCall]:
        """FIXED: Convert JSON to ToolCall schema with enhanced field extraction."""
        if not isinstance(json_data, dict):
            return None
        
        # Extract tool name with multiple field options
        tool_name = None
        for name_field in ["name", "tool", "function_name", "function"]:
            if name_field in json_data:
                if name_field == "function" and isinstance(json_data[name_field], dict):
                    # Handle Ollama function format
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
        call_id = json_data.get("id")
        if not call_id:
            call_id = f"extracted_{int(time.time() * 1000000)}_{hash(tool_name) % 10000}"
        
        return ToolCall.create(
            name=tool_name,
            arguments=params,
            id=call_id
        )

    # Backward compatibility method
    def extract_tool_calls(self, message: MessageProtocol) -> List[Dict[str, Any]]:
        """Backward compatibility method returning dict format."""
        schema_calls = self.extract_tool_calls_to_schema(message.content or "")
        return [tc.to_dict() for tc in schema_calls]

    def extract_native_tool_calls(self, response_data: Dict[str, Any]) -> List[ToolCall]:
        """FIXED: Extract native tool calls from Ollama response format."""
        tool_calls = []
        
        # Check for tool calls in message
        message = response_data.get("message", {})
        if "tool_calls" in message:
            for raw_tc in message["tool_calls"]:
                try:
                    # Handle Ollama's native tool call format
                    if "function" in raw_tc:
                        func_data = raw_tc["function"]
                        tool_call = ToolCall.create(
                            name=func_data.get("name", ""),
                            arguments=func_data.get("arguments", {}),
                            id=raw_tc.get("id", f"native_{int(time.time() * 1000000)}_{len(tool_calls)}")
                        )
                        tool_calls.append(tool_call)
                    else:
                        # Direct format
                        tool_call = ToolCall.from_dict(raw_tc)
                        tool_calls.append(tool_call)
                except Exception as e:
                    pass
        
        return tool_calls
