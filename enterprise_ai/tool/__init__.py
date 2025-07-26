"""
Enterprise AI Tools Package

This package provides a collection of tools for various AI operations with
unified LLM integration support and comprehensive configuration management.
"""

# Import core components (simplified)
from enterprise_ai.tool.core import (
    BaseTool,
    ToolError,
    ToolConfig,
    ToolCapability,
    ToolState,
    ToolCollection,
    get_all_tools,
    get_tool_by_name,
    get_tool_names,
    create_tool_instance,
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

# Tool modules (lazy loaded to avoid import errors with optional dependencies)
def get_available_tools():
    """Get available tools with graceful handling of missing dependencies."""
    from enterprise_ai.tool.simple_loader import get_all_tools
    return get_all_tools()

def get_tool_by_name(name: str):
    """Get a specific tool by name with lazy loading."""
    from enterprise_ai.tool.simple_loader import get_tool_by_name
    return get_tool_by_name(name)

# Lazy imports for individual tools (only import when needed)
def _lazy_import_tool(module_path: str, class_name: str):
    """Helper for lazy importing tools."""
    try:
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    except ImportError:
        return None

# Make tools available through lazy getters
def get_web_search():
    return _lazy_import_tool('enterprise_ai.tool.research.web_search', 'WebSearch')

def get_deep_research():
    return _lazy_import_tool('enterprise_ai.tool.research.deep_research', 'DeepResearch')

def get_browser_tool():
    return _lazy_import_tool('enterprise_ai.tool.browser.browser', 'BrowserUseTool')

def get_planning_tool():
    return _lazy_import_tool('enterprise_ai.tool.planning.planning', 'PlanningTool')

def get_python_execute():
    return _lazy_import_tool('enterprise_ai.tool.execution.python', 'PythonExecute')

def get_bash_tool():
    return _lazy_import_tool('enterprise_ai.tool.execution.bash', 'Bash')

def get_process_manager():
    return _lazy_import_tool('enterprise_ai.tool.execution.process', 'ProcessManagerTool')

def get_file_editor():
    return _lazy_import_tool('enterprise_ai.tool.file.editor', 'FileEditor')

def get_file_system_tool():
    return _lazy_import_tool('enterprise_ai.tool.file.filesystem', 'FileSystemTool')

def get_code_search_tool():
    return _lazy_import_tool('enterprise_ai.tool.file.search', 'CodeSearchTool')

def get_chat_completion():
    return _lazy_import_tool('enterprise_ai.tool.content.chat_completion', 'CreateChatCompletion')

def get_terminate_tool():
    return _lazy_import_tool('enterprise_ai.tool.utility.terminate', 'TerminateTool')

def get_mime_type_tool():
    return _lazy_import_tool('enterprise_ai.tool.utility.mime_types', 'MimeTypeTool')

__all__ = [
    # Core components (simplified)
    "BaseTool",
    "ToolError",
    "ToolConfig",
    "ToolCapability", 
    "ToolState",
    "ToolCollection",
    "get_all_tools",
    "get_tool_by_name", 
    "get_tool_names",
    "create_tool_instance",
    
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
    
    # Lazy loading functions (NEW - replaces direct imports)
    "get_available_tools",
    "get_tool_by_name",
    "get_web_search",
    "get_deep_research", 
    "get_browser_tool",
    "get_planning_tool",
    "get_python_execute",
    "get_bash_tool",
    "get_process_manager",
    "get_file_editor",
    "get_file_system_tool", 
    "get_code_search_tool",
    "get_chat_completion",
    "get_terminate_tool",
    "get_mime_type_tool",
]