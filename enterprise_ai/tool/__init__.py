"""
Enterprise AI Tools Package

This package provides a collection of tools for various AI operations with
unified LLM integration support and comprehensive configuration management.
"""

# Import core components (unified system)
from enterprise_ai.tool.core import (
    BaseTool,
    ToolError,
    ToolConfig,
    ToolCapability,
    ToolState,
    ToolCollection,
    register_tool,
    get_registry,
    ToolRegistry,
)

# Import unified result system
from enterprise_ai.tool.core.result import ToolResult, CLIResult, ToolFailure, ToolResultMetadata

# Import LLM integration
from enterprise_ai.tool.core.llm_adapter import (
    LLMToolAdapter,
    get_llm_tools,
    get_llm_tool_definitions,
)

# Import configuration management system
from enterprise_ai.tool.core.config_manager import (
    ConfigManager,
    get_config_manager,
    get_config,
    get_config_value,
    set_config_value,
    validate_path_config,
    is_command_blocked_config,
)
from enterprise_ai.tool.core.config_tool import ConfigurationTool

# Import tool modules
from enterprise_ai.tool import browser
from enterprise_ai.tool import content
from enterprise_ai.tool import execution
from enterprise_ai.tool import file
from enterprise_ai.tool import planning
from enterprise_ai.tool import research
from enterprise_ai.tool import utility

# Import enhanced and existing tools
from enterprise_ai.tool.research.web_search import WebSearch
from enterprise_ai.tool.research.deep_research import DeepResearch
from enterprise_ai.tool.browser.browser import BrowserUseTool
from enterprise_ai.tool.planning.planning import PlanningTool
from enterprise_ai.tool.execution.python import PythonExecute
from enterprise_ai.tool.execution.bash import Bash
from enterprise_ai.tool.execution.process import ProcessManagerTool
from enterprise_ai.tool.file.editor import FileEditor  
from enterprise_ai.tool.file.filesystem import FileSystemTool  
from enterprise_ai.tool.file.search import CodeSearchTool
from enterprise_ai.tool.content.chat_completion import CreateChatCompletion
from enterprise_ai.tool.utility.terminate import TerminateTool
from enterprise_ai.tool.utility.mime_types import MimeTypeTool

__all__ = [
    # Core components (unified)
    "BaseTool",
    "ToolError",
    "ToolConfig",
    "ToolCapability", 
    "ToolState",
    "ToolCollection",
    "register_tool",
    "get_registry",
    "ToolRegistry",
    
    # Unified result system
    "ToolResult",
    "CLIResult", 
    "ToolFailure",
    "ToolResultMetadata",
    
    # LLM Integration
    "LLMToolAdapter",
    "get_llm_tools",
    "get_llm_tool_definitions",
    
    # Configuration Management System
    "ConfigManager",
    "ConfigurationTool",
    "get_config_manager",
    "get_config",
    "get_config_value",
    "set_config_value", 
    "validate_path_config",
    "is_command_blocked_config",
    
    # Tool modules
    "browser",
    "content", 
    "execution",
    "file",
    "planning",
    "research",
    "utility",
    
    # Enhanced and existing tools
    "WebSearch",
    "DeepResearch", 
    "BrowserUseTool",
    "PlanningTool",
    "PythonExecute",  # Current implementation (could be enhanced later)
    "Bash",  
    "ProcessManagerTool",
    "FileEditor",  
    "FileSystemTool", 
    "CodeSearchTool",
    "CreateChatCompletion",
    "TerminateTool",
    "MimeTypeTool",
]