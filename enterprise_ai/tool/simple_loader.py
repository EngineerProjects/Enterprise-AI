"""
Simplified tool loading for Enterprise AI.

Direct imports instead of complex registry system.
"""

from typing import Dict, List, Type, Any

from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.simple_loader")


# Direct tool imports - no complex registry needed
def get_all_tools() -> Dict[str, Type[BaseTool]]:
    """
    Get all available tools through direct imports.
    
    This replaces the complex registry system with simple imports.
    """
    tools = {}
    
    try:
        # Core tools
        from enterprise_ai.tool.file.editor import FileEditor
        from enterprise_ai.tool.file.filesystem import FileSystemTool
        from enterprise_ai.tool.file.search import CodeSearchTool
        tools.update({
            'file_editor': FileEditor,
            'file_system': FileSystemTool,
            'code_search': CodeSearchTool,
        })
    except ImportError as e:
        logger.warning(f"Could not import file tools: {e}")
    
    try:
        # Execution tools
        from enterprise_ai.tool.execution.python import PythonExecute
        from enterprise_ai.tool.execution.bash import Bash
        from enterprise_ai.tool.execution.process import ProcessManagerTool
        tools.update({
            'python_execute': PythonExecute,
            'bash': Bash,
            'process_manager': ProcessManagerTool,
        })
    except ImportError as e:
        logger.warning(f"Could not import execution tools: {e}")
    
    try:
        # Research tools
        from enterprise_ai.tool.research.web_search import WebSearch
        from enterprise_ai.tool.research.deep_research import DeepResearch
        tools.update({
            'web_search': WebSearch,
            'deep_research': DeepResearch,
        })
    except ImportError as e:
        logger.warning(f"Could not import research tools: {e}")
    
    try:
        # Browser tools
        from enterprise_ai.tool.browser.browser import BrowserUseTool
        tools.update({
            'browser': BrowserUseTool,
        })
    except ImportError as e:
        logger.warning(f"Could not import browser tools: {e}")
    
    try:
        # Content tools
        from enterprise_ai.tool.content.chat_completion import CreateChatCompletion
        tools.update({
            'chat_completion': CreateChatCompletion,
        })
    except ImportError as e:
        logger.warning(f"Could not import content tools: {e}")
    
    try:
        # Utility tools
        from enterprise_ai.tool.utility.terminate import TerminateTool
        from enterprise_ai.tool.utility.mime_types import MimeTypeTool
        from enterprise_ai.tool.utility.config_tool import ConfigurationTool
        tools.update({
            'terminate': TerminateTool,
            'mime_types': MimeTypeTool,
            'configuration': ConfigurationTool,
        })
    except ImportError as e:
        logger.warning(f"Could not import utility tools: {e}")
    
    try:
        # Planning tools
        from enterprise_ai.tool.planning.planning import PlanningTool
        tools.update({
            'planning': PlanningTool,
        })
    except ImportError as e:
        logger.warning(f"Could not import planning tools: {e}")
    
    logger.info(f"Loaded {len(tools)} tools via direct imports")
    return tools


def get_tool_by_name(name: str) -> Type[BaseTool]:
    """Get a specific tool class by name."""
    tools = get_all_tools()
    if name not in tools:
        raise ValueError(f"Tool '{name}' not found. Available: {list(tools.keys())}")
    return tools[name]


def get_tool_names() -> List[str]:
    """Get list of available tool names."""
    return list(get_all_tools().keys())


def create_tool_instance(name: str, **kwargs) -> BaseTool:
    """Create a tool instance by name."""
    tool_class = get_tool_by_name(name)
    return tool_class(**kwargs)
