"""
Enhanced Simple Tool Loader with selective loading to prevent unnecessary tool initialization.

FIXED: Only loads requested tools instead of importing all tools when only one is needed.
"""

from typing import Dict, Type, List
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.logger import get_logger

logger = get_logger("tool.simple_loader")


# Tool mapping for selective loading
TOOL_MAPPING = {
    # File tools
    'file_editor': ('enterprise_ai.tool.file.editor', 'FileEditor'),
    'file_system': ('enterprise_ai.tool.file.filesystem', 'FileSystemTool'),
    'code_search': ('enterprise_ai.tool.file.search', 'CodeSearchTool'),
    
    # Execution tools
    'python_execute': ('enterprise_ai.tool.execution.python', 'PythonExecute'),
    'bash': ('enterprise_ai.tool.execution.bash', 'Bash'),
    'process_manager': ('enterprise_ai.tool.execution.process', 'ProcessManagerTool'),
    
    # Research tools (these were causing the annoying logs)
    'web_search': ('enterprise_ai.tool.research.web_search', 'WebSearch'),
    'deep_research': ('enterprise_ai.tool.research.deep_research', 'DeepResearch'),
    
    # Browser tools
    'browser': ('enterprise_ai.tool.browser.browser', 'BrowserUseTool'),
    
    # Content tools
    'chat_completion': ('enterprise_ai.tool.content.chat_completion', 'CreateChatCompletion'),
    
    # Planning tools
    'planning': ('enterprise_ai.tool.planning.planning', 'PlanningTool'),
    
    # Utility tools
    'terminate': ('enterprise_ai.tool.utility.terminate', 'TerminateTool'),
    'mime_types': ('enterprise_ai.tool.utility.mime_types', 'MimeTypeTool'),
    'configuration': ('enterprise_ai.tool.utility.config_tool', 'ConfigurationTool'),
}


def get_tool_by_name_selective(name: str) -> Type[BaseTool]:
    """
    Get a specific tool class by name without loading all tools.
    
    FIXED: Only imports the requested tool instead of all tools.
    """
    if name not in TOOL_MAPPING:
        available = list(TOOL_MAPPING.keys())
        raise ValueError(f"Tool '{name}' not found. Available: {available}")
    
    module_path, class_name = TOOL_MAPPING[name]
    
    try:
        # Import only the specific tool module
        module = __import__(module_path, fromlist=[class_name])
        tool_class = getattr(module, class_name)
        logger.debug(f"Selectively loaded tool: {name}")
        return tool_class
    except ImportError as e:
        logger.error(f"Could not import tool {name} from {module_path}: {e}")
        raise
    except AttributeError as e:
        logger.error(f"Tool class {class_name} not found in {module_path}: {e}")
        raise


def get_specific_tools(tool_names: List[str]) -> Dict[str, Type[BaseTool]]:
    """
    Get only the requested tools without loading others.
    
    FIXED: Selective loading to prevent research tool initialization spam.
    """
    tools = {}
    
    for name in tool_names:
        try:
            tools[name] = get_tool_by_name_selective(name)
        except Exception as e:
            logger.warning(f"Failed to load requested tool {name}: {e}")
    
    logger.info(f"Loaded {len(tools)} requested tools (selective loading)")
    return tools


def get_all_tools() -> Dict[str, Type[BaseTool]]:
    """
    Get all available tools through direct imports.
    
    This is the original implementation - loads ALL tools.
    Use get_specific_tools() for selective loading.
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
        # Planning tools
        from enterprise_ai.tool.planning.planning import PlanningTool
        tools.update({
            'planning': PlanningTool,
        })
    except ImportError as e:
        logger.warning(f"Could not import planning tools: {e}")
    
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
    
    logger.info(f"Loaded {len(tools)} tools via direct imports")
    return tools


def get_tool_by_name(name: str) -> Type[BaseTool]:
    """Get a specific tool class by name (original implementation)."""
    tools = get_all_tools()
    if name not in tools:
        raise ValueError(f"Tool '{name}' not found. Available: {list(tools.keys())}")
    return tools[name]


def get_tool_names() -> List[str]:
    """Get list of available tool names."""
    return list(TOOL_MAPPING.keys())


def create_tool_instance(name: str, **kwargs) -> BaseTool:
    """Create a tool instance by name using selective loading."""
    tool_class = get_tool_by_name_selective(name)
    return tool_class(**kwargs)
