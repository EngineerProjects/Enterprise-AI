"""
Enhanced logging system for Enterprise AI with performance optimizations.
Provides three-tier logging: Clean Terminal, Tool Verbose, Debug File
"""

import logging
import os
import sys
import json
from typing import Dict, Optional, Any, Union
from pathlib import Path
from datetime import datetime

# Performance optimization: Cache debug state
_DEBUG_ENABLED = os.getenv('ENTERPRISE_AI_DEBUG', '').lower() == 'true'


class Colors:
    """Terminal color codes for clean output formatting."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Standard colors
    BLACK = '\033[30m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    
    # Background colors
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'


class LogLevel:
    """Log level constants for better performance."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40


class PerformantLogger:
    """
    High-performance logger with three-tier system:
    1. Clean Terminal (errors, prompts, results only)
    2. Tool Verbose (formatted tool execution flow)
    3. Debug File (complete debug information)
    """
    
    def __init__(self, name: str, config: Optional[Dict] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        self.config = config or {}
        
        # Performance optimization: Cache level checks
        self._debug_enabled = self.logger.isEnabledFor(logging.DEBUG)
        self._info_enabled = self.logger.isEnabledFor(logging.INFO)
        
        # Three-tier configuration
        self.clean_terminal = self.config.get('clean_terminal', True)
        self.tool_verbose = self.config.get('tool_verbose', False)
        self.debug_file = self.config.get('debug_file', None)
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup the three-tier handler system."""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # 1. Clean Terminal Handler (errors and essential info only)
        if self.clean_terminal:
            terminal_handler = logging.StreamHandler(sys.stdout)
            terminal_handler.setLevel(logging.ERROR)
            terminal_formatter = logging.Formatter(
                f'{Colors.RED}%(levelname)s{Colors.RESET}: %(message)s'
            )
            terminal_handler.setFormatter(terminal_formatter)
            self.logger.addHandler(terminal_handler)
        
        # 2. Tool Verbose Handler (colorful tool execution)
        if self.tool_verbose:
            verbose_handler = logging.StreamHandler(sys.stdout)
            verbose_handler.setLevel(logging.INFO)
            verbose_formatter = logging.Formatter(
                f'{Colors.CYAN}[%(name)s]{Colors.RESET} %(message)s'
            )
            verbose_handler.setFormatter(verbose_formatter)
            self.logger.addHandler(verbose_handler)
        
        # 3. Debug File Handler (complete logging)
        if self.debug_file:
            os.makedirs(os.path.dirname(self.debug_file), exist_ok=True)
            file_handler = logging.FileHandler(self.debug_file)
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def debug(self, msg: str, *args, **kwargs):
        """Optimized debug logging with lazy evaluation."""
        if self._debug_enabled:
            self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Optimized info logging."""
        if self._info_enabled:
            self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Warning logging."""
        self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """Error logging."""
        self.logger.error(msg, *args, **kwargs)
    
    # High-performance category-specific methods
    def debug_tool(self, msg: str, *args):
        """Tool-specific debug (can be disabled separately)."""
        if _DEBUG_ENABLED and self._debug_enabled:
            self.logger.debug(f"[TOOL] {msg}", *args)
    
    def debug_llm(self, msg: str, *args):
        """LLM-specific debug (can be disabled separately)."""
        if _DEBUG_ENABLED and self._debug_enabled:
            self.logger.debug(f"[LLM] {msg}", *args)
    
    def debug_sandbox(self, msg: str, *args):
        """Sandbox-specific debug (can be disabled separately)."""
        if _DEBUG_ENABLED and self._debug_enabled:
            self.logger.debug(f"[SANDBOX] {msg}", *args)
    
    # Clean terminal output methods
    def user_prompt(self, msg: str):
        """Clean user prompt output."""
        print(f"{Colors.BOLD}{Colors.BLUE}➤{Colors.RESET} {msg}")
    
    def success(self, msg: str):
        """Clean success message."""
        print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")
    
    def status(self, msg: str):
        """Clean status update."""
        print(f"{Colors.YELLOW}•{Colors.RESET} {msg}")
    
    def tool_execution(self, tool_name: str, args: Dict[str, Any]):
        """Formatted tool execution display."""
        if self.tool_verbose:
            print(f"\n{Colors.BG_BLUE}{Colors.WHITE} 🔧 TOOL EXECUTION {Colors.RESET}")
            print(f"{Colors.BOLD}Tool:{Colors.RESET} {Colors.CYAN}{tool_name}{Colors.RESET}")
            
            if args:
                print(f"{Colors.BOLD}Arguments:{Colors.RESET}")
                for key, value in args.items():
                    # Smart truncation for large values
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:97] + "..."
                    print(f"  {Colors.YELLOW}{key}:{Colors.RESET} {value_str}")
            print(f"{Colors.BLUE}{'─' * 50}{Colors.RESET}\n")
    
    def tool_result(self, result: Any, success: bool = True):
        """Formatted tool result display."""
        if self.tool_verbose:
            status_icon = "✓" if success else "✗"
            status_color = Colors.GREEN if success else Colors.RED
            
            print(f"{status_color}{status_icon} Tool completed{Colors.RESET}")
            
            # Smart JSON formatting for structured results
            if isinstance(result, (dict, list)):
                try:
                    formatted = json.dumps(result, indent=2)[:500]
                    if len(formatted) >= 500:
                        formatted += "\n... (truncated)"
                    print(f"{Colors.DIM}{formatted}{Colors.RESET}\n")
                except:
                    print(f"{Colors.DIM}{str(result)[:200]}{Colors.RESET}\n")
            else:
                result_str = str(result)[:200]
                if len(str(result)) > 200:
                    result_str += "... (truncated)"
                print(f"{Colors.DIM}{result_str}{Colors.RESET}\n")


# Performance optimized utility functions
def debug_log(logger: PerformantLogger, msg: str, *args):
    """Zero-overhead debug logging when disabled."""
    if _DEBUG_ENABLED and logger._debug_enabled:
        logger.debug(msg, *args)


def conditional_debug(logger: PerformantLogger, condition: bool, msg: str, *args):
    """Only log debug if condition is true and debug is enabled."""
    if condition and _DEBUG_ENABLED and logger._debug_enabled:
        logger.debug(msg, *args)


# Cache for logger instances
_logger_cache: Dict[str, PerformantLogger] = {}


def get_optimized_logger(name: str, config: Optional[Dict] = None) -> PerformantLogger:
    """Get cached logger instance for better performance."""
    cache_key = f"{name}_{hash(str(config) if config else '')}"
    
    if cache_key not in _logger_cache:
        _logger_cache[cache_key] = PerformantLogger(name, config)
    
    return _logger_cache[cache_key]


def setup_enterprise_logging(
    debug_file: Optional[str] = None,
    tool_verbose: bool = False,
    clean_terminal: bool = True
) -> Dict[str, Any]:
    """
    Setup enterprise-wide logging configuration.
    
    Args:
        debug_file: Path to debug log file (None disables file logging)
        tool_verbose: Enable verbose tool execution display
        clean_terminal: Enable clean terminal output
    
    Returns:
        Configuration dictionary
    """
    config = {
        'debug_file': debug_file,
        'tool_verbose': tool_verbose,
        'clean_terminal': clean_terminal,
        'timestamp': datetime.now().isoformat()
    }
    
    # Set global debug state
    global _DEBUG_ENABLED
    _DEBUG_ENABLED = debug_file is not None or tool_verbose
    
    return config
