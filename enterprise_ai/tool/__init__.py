"""
Enterprise AI Tools Package

This package provides a collection of tools for various AI operations including:
- Browser automation
- Content generation
- File operations
- Execution environments
- Planning and task management
- Research capabilities
- Utility functions
"""

# Import core components
from enterprise_ai.tool.core import (
    BaseTool,
    ToolError,
    ToolResult,
    CLIResult,
    ToolFailure,
    ToolCollection,
    register_tool,
    get_registry,
    ToolRegistry,
)

# Import tool modules
from enterprise_ai.tool import browser
from enterprise_ai.tool import content
from enterprise_ai.tool import execution
from enterprise_ai.tool import file
from enterprise_ai.tool import planning
from enterprise_ai.tool import research
from enterprise_ai.tool import utility

# Define the public API of the package
from enterprise_ai.tool.execution.python import PythonExecute
from enterprise_ai.tool.execution.bash import Bash
from enterprise_ai.tool.file.editor import FileEditor
from enterprise_ai.tool.research.web_search import WebSearch
from enterprise_ai.tool.research.deep_research import DeepResearch
from enterprise_ai.tool.browser.browser import BrowserUseTool
from enterprise_ai.tool.content.chat_completion import CreateChatCompletion
from enterprise_ai.tool.planning.planning import PlanningTool
from enterprise_ai.tool.utility.terminate import Terminate


__all__ = [
    # Core components
    "BaseTool",
    "ToolError",
    "ToolResult",
    "CLIResult",
    "ToolFailure",
    "ToolCollection",
    "register_tool",
    "get_registry",
    "ToolRegistry",
    # Tool modules
    "browser",
    "content",
    "execution",
    "file",
    "planning",
    "research",
    "utility",
    # Specific tools
    'PythonExecute',
    'Bash', 
    'FileEditor',
    'WebSearch',
    'DeepResearch',
    'BrowserUseTool',
    'CreateChatCompletion',
    'PlanningTool',
    'Terminate'
]
