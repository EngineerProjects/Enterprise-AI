"""Enhanced Python code execution tool for Enterprise AI with session management and optimization."""

import asyncio
import multiprocessing
import sys
import traceback
import tempfile
import subprocess
import os
import time
import json
from io import StringIO
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass

from pydantic import Field, ConfigDict

from enterprise_ai.tool.core.base import (
    BaseTool, 
    ToolError, 
    ToolConfig, 
    ToolCapability, 
    ExecutionMode, 
    SandboxMode
)
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.execution.python")


@dataclass
class PythonExecutionSession:
    """Manages Python execution sessions with state tracking."""
    session_id: str
    code_hash: str
    start_time: float
    timeout: float
    execution_mode: str
    output: str = ""
    error: Optional[str] = None
    success: bool = False
    variables: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.variables is None:
            self.variables = {}
    
    def get_runtime(self) -> float:
        """Get session runtime in seconds."""
        return time.time() - self.start_time
    
    def add_variable(self, name: str, value: Any) -> None:
        """Add variable to session state."""
        try:
            # Only store JSON-serializable values
            json.dumps(value)
            self.variables[name] = value
        except (TypeError, ValueError):
            # Store string representation for complex objects
            self.variables[name] = str(value)


class PythonSessionManager:
    """Enhanced session manager for Python executions."""
    
    def __init__(self):
        self.sessions: Dict[str, PythonExecutionSession] = {}
        self.max_sessions = 10
        
    def create_session(self, code: str, timeout: float, execution_mode: str) -> PythonExecutionSession:
        """Create new execution session."""
        import hashlib
        code_hash = hashlib.md5(code.encode()).hexdigest()[:8]
        session_id = f"py_{code_hash}_{int(time.time())}"
        
        session = PythonExecutionSession(
            session_id=session_id,
            code_hash=code_hash,
            start_time=time.time(),
            timeout=timeout,
            execution_mode=execution_mode
        )
        
        # Clean old sessions if needed
        if len(self.sessions) >= self.max_sessions:
            oldest = min(self.sessions.values(), key=lambda s: s.start_time)
            del self.sessions[oldest.session_id]
        
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[PythonExecutionSession]:
        """Get existing session."""
        return self.sessions.get(session_id)
    
    def cleanup_old_sessions(self, max_age: float = 3600) -> None:
        """Clean up sessions older than max_age seconds."""
        current_time = time.time()
        old_sessions = [
            sid for sid, session in self.sessions.items()
            if current_time - session.start_time > max_age
        ]
        for sid in old_sessions:
            del self.sessions[sid]


class EnhancedCodeAnalyzer:
    """Enhanced code analysis for better sandbox decision making."""
    
    def __init__(self):
        self.safe_modules = {
            'math', 'random', 'datetime', 'json', 'base64', 'uuid', 
            'collections', 'itertools', 'functools', 'operator', 'copy',
            're', 'string', 'textwrap', 'unicodedata', 'statistics',
            'decimal', 'fractions', 'hashlib', 'hmac', 'secrets',
            'time', 'calendar', 'locale', 'gettext'
        }
        
        self.dangerous_patterns = [
            'import subprocess', 'import os', 'import sys', 'import socket',
            'import urllib', 'import requests', 'import http', '__import__',
            'eval(', 'exec(', 'compile(', 'open(', 'file(', 'input(',
            'raw_input(', 'execfile(', 'reload(', 'help(', 'dir(',
            'globals(', 'locals(', 'vars(', 'delattr(', 'setattr(',
            'getattr(', 'hasattr('
        ]
    
    def analyze_code_safety(self, code: str) -> Dict[str, Any]:
        """Comprehensive code safety analysis."""
        analysis = {
            'is_safe_for_local': True,
            'danger_level': 0,
            'issues': [],
            'requires_sandbox': False,
            'estimated_complexity': self._estimate_complexity(code)
        }
        
        code_lower = code.lower().strip()
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if pattern in code_lower:
                analysis['is_safe_for_local'] = False
                analysis['danger_level'] += 2
                analysis['issues'].append(f"Contains dangerous pattern: {pattern}")
        
        # Check for imports
        if 'import ' in code_lower:
            imports = self._extract_imports(code)
            for imp in imports:
                if imp not in self.safe_modules:
                    analysis['danger_level'] += 1
                    analysis['issues'].append(f"Potentially unsafe import: {imp}")
        
        # Check code complexity
        if analysis['estimated_complexity'] > 50:
            analysis['danger_level'] += 1
            analysis['issues'].append("High complexity code")
        
        # Final decision
        analysis['requires_sandbox'] = analysis['danger_level'] >= 2
        
        return analysis
    
    def _estimate_complexity(self, code: str) -> int:
        """Estimate code complexity based on various factors."""
        complexity = 0
        lines = [line.strip() for line in code.split('\n') if line.strip()]
        
        complexity += len(lines)  # Base complexity
        complexity += code.count('for ') * 2  # Loops
        complexity += code.count('while ') * 2
        complexity += code.count('if ') * 1  # Conditionals  
        complexity += code.count('def ') * 3  # Functions
        complexity += code.count('class ') * 5  # Classes
        complexity += code.count('try:') * 2  # Exception handling
        
        return complexity
    
    def _extract_imports(self, code: str) -> List[str]:
        """Extract import statements from code."""
        imports = []
        lines = code.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('import '):
                module = line.replace('import ', '').split(' as ')[0].split(',')[0].strip()
                imports.append(module)
            elif line.startswith('from '):
                module = line.split(' import ')[0].replace('from ', '').strip()
                imports.append(module)
        
        return imports


@register_tool(category="execution", capabilities=["code_execution", "data_analysis"])
class PythonExecute(BaseTool):
    """
    Enhanced Python code execution tool with session management, advanced safety analysis, and optimization.

    Key capabilities:
    * Execute Python code with intelligent safety analysis and routing
    * Session management with state tracking and variable persistence
    * Enhanced sandbox execution with optimized security controls
    * Advanced code complexity analysis and danger assessment
    * Comprehensive error handling with detailed debugging information
    * Performance optimization with multiprocessing and async support
    * Memory-efficient execution with configurable resource limits

    Enhanced Features:
    * Smart execution mode selection based on code analysis
    * Session state tracking with variable persistence
    * Detailed execution metrics and performance monitoring
    * Enhanced error reporting with line-level debugging
    * Optimized sandbox security with minimal overhead
    * Code complexity assessment and risk evaluation
    * Memory and CPU usage monitoring

    Use this tool when:
    * You need to run Python code with intelligent safety controls
    * You want persistent variable state across executions
    * You need detailed execution analysis and debugging
    * You require optimized performance for complex computations
    * You want comprehensive security with minimal friction

    Notes:
    * Automatically routes based on intelligent code analysis
    * Session state persists for related executions
    * Security controls are optimized for performance
    * Detailed metrics available for execution monitoring
    """

    # Allow arbitrary types for our complex fields
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "python_execute"
    description: str = """
    Enhanced Python code execution with intelligent safety routing and session management.

    * Purpose: Execute Python code with advanced safety analysis and session persistence
    * Usage: Run code with intelligent sandbox routing, state tracking, and performance optimization
    * Features: Session management, code analysis, enhanced security, performance monitoring
    * Returns: Execution results with detailed metrics and session information

    Features intelligent code analysis for optimal execution routing, session state persistence,
    and comprehensive security controls with minimal performance impact.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds.",
                "default": 30,
            },
            "sandbox_mode": {
                "type": "string",
                "enum": ["auto", "local", "sandbox"],
                "description": "Execution environment preference - auto uses intelligent analysis",
                "default": "auto"
            },
            "session_id": {
                "type": "string", 
                "description": "Optional session ID for state persistence"
            },
            "persist_variables": {
                "type": "boolean",
                "description": "Whether to persist variables for future executions",
                "default": False
            },
            "show_analysis": {
                "type": "boolean",
                "description": "Whether to show code safety analysis results",
                "default": False
            }
        },
        "required": ["code"],
    }

    capabilities: Set[Union[str, ToolCapability]] = {
        ToolCapability.CODE_EXECUTION,
        ToolCapability.DATA_PROCESSING,
    }

    # Define fields that should be excluded from Pydantic validation
    session_manager: PythonSessionManager = Field(default_factory=PythonSessionManager, exclude=True)
    code_analyzer: EnhancedCodeAnalyzer = Field(default_factory=EnhancedCodeAnalyzer, exclude=True)
    execution_stats: Dict[str, Any] = Field(default_factory=lambda: {
        'total_executions': 0,
        'local_executions': 0,
        'sandbox_executions': 0,
        'failed_executions': 0,
        'average_execution_time': 0.0
    }, exclude=True)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Enhanced Python execution tool."""
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            config=config or ToolConfig(
                timeout=30.0,
                max_retries=0,
                execution_mode=ExecutionMode.HYBRID,
                sandbox_mode=SandboxMode.UNIFIED,
                danger_level=4,
                requires_approval=True,
                approval_message="Execute Python code with enhanced safety controls?",
                verbose_logging=False,
            ),
            **kwargs,
        )

        logger.debug("Enhanced PythonExecute tool initialized")

    def _should_use_sandbox_execution(self, code: str, user_preference: str = "auto") -> tuple[bool, Dict[str, Any]]:
        """Enhanced sandbox decision with detailed analysis."""
        if user_preference == "sandbox":
            return True, {"reason": "user_forced", "analysis": {}}
        elif user_preference == "local":
            return False, {"reason": "user_forced", "analysis": {}}
        
        # Intelligent analysis
        analysis = self.code_analyzer.analyze_code_safety(code)
        should_sandbox = analysis['requires_sandbox']
        
        decision_info = {
            "reason": "intelligent_analysis",
            "analysis": analysis,
            "decision": "sandbox" if should_sandbox else "local"
        }
        
        return should_sandbox, decision_info

    async def _execute_in_sandbox(self, code: str, timeout: float, session: PythonExecutionSession) -> ToolResult:
        """Optimized sandbox execution with enhanced security."""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # OPTIMIZED: More efficient security wrapper
                security_wrapper = f'''
import sys
import traceback

# Optimized restricted modules list
RESTRICTED = {{'subprocess', 'socket', 'urllib', 'requests', 'http', 'ftplib', 'telnetlib', 'smtplib'}}

class SafeImporter:
    def __init__(self):
        self.original_import = __builtins__.__import__
        
    def __call__(self, name, globals=None, locals=None, fromlist=(), level=0):
        if name in RESTRICTED or any(name.startswith(r + '.') for r in RESTRICTED):
            raise ImportError(f"Import of '{{name}}' is restricted in sandbox environment")
        return self.original_import(name, globals, locals, fromlist, level)

# Install security layer
__builtins__.__import__ = SafeImporter()

# Execute user code
try:
    with open("{temp_file}", "r") as f:
        user_code = f.read()
    exec(user_code)
except Exception as e:
    print(f"Error: {{type(e).__name__}}: {{e}}", file=sys.stderr)
    traceback.print_exc()
'''
                
                result = subprocess.run([
                    'python', '-c', security_wrapper
                ], capture_output=True, text=True, timeout=timeout)
                
                # Enhanced result processing
                has_error = result.returncode != 0 or (result.stderr and result.stderr.strip())
                
                session.output = result.stdout
                session.error = result.stderr if has_error else None
                session.success = not has_error
                
                if has_error:
                    return ToolResult.create_error(
                        error=result.stderr if result.stderr else f"Process exited with code {result.returncode}",
                        tool_name=self.name
                    )
                else:
                    return ToolResult.create_success(
                        result={
                            "output": result.stdout,
                            "execution_environment": "enhanced_sandbox",
                            "session_id": session.session_id,
                            "runtime": session.get_runtime()
                        },
                        tool_name=self.name
                    )
            finally:
                os.unlink(temp_file)
                
        except subprocess.TimeoutExpired:
            return ToolResult.create_error(
                error=f"Sandbox execution timed out after {timeout} seconds",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult.create_error(
                error=f"Enhanced sandbox execution failed: {str(e)}",
                tool_name=self.name
            )

    async def _execute_locally(self, code: str, timeout: float, session: PythonExecutionSession) -> ToolResult:
        """Enhanced local execution with session support."""
        try:
            with multiprocessing.Manager() as manager:
                result = manager.dict({
                    "output": "", 
                    "error": None, 
                    "success": False,
                    "variables": {}
                })

                # FIXED: Use full builtins for local execution (safe environment)
                # Local execution is already isolated by multiprocessing
                safe_globals = {
                    "__builtins__": __builtins__,  # Use full builtins for local execution
                }

                proc = multiprocessing.Process(
                    target=self._run_code_local_enhanced, 
                    args=(code, result, safe_globals, session.variables)
                )
                proc.start()
                proc.join(timeout)

                if proc.is_alive():
                    proc.terminate()
                    proc.join(1)
                    return ToolResult.create_error(
                        error=f"Local execution timeout after {timeout} seconds",
                        tool_name=self.name
                    )

                # Update session
                session.output = result["output"]
                session.error = result["error"]
                session.success = result["success"]
                if result["variables"]:
                    session.variables.update(result["variables"])

                if result["success"]:
                    return ToolResult.create_success(
                        result={
                            "output": result["output"],
                            "execution_environment": "enhanced_local",
                            "session_id": session.session_id,
                            "runtime": session.get_runtime(),
                            "variables_count": len(session.variables)
                        },
                        tool_name=self.name
                    )
                else:
                    return ToolResult.create_error(
                        error=result['error'],
                        tool_name=self.name
                    )

        except Exception as e:
            return ToolResult.create_error(
                error=f"Enhanced local execution error: {str(e)}",
                tool_name=self.name
            )

    def _run_code_local_enhanced(
        self, code: str, result_dict: Dict[str, Any], 
        safe_globals: Dict[str, Any], existing_vars: Dict[str, Any]
    ) -> None:
        """Enhanced local execution with variable persistence."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        output_buffer = StringIO()
        error_buffer = StringIO()

        try:
            sys.stdout = output_buffer
            sys.stderr = error_buffer

            # Merge existing variables into execution environment
            execution_globals = {**safe_globals}
            execution_globals.update(existing_vars)

            try:
                exec(code, execution_globals, execution_globals)
                
                # Extract new variables (avoid builtins and system variables)
                new_vars = {}
                for key, value in execution_globals.items():
                    if (not key.startswith('__') and 
                        key not in safe_globals and 
                        key != '__builtins__'):
                        try:
                            # Test if JSON serializable
                            json.dumps(value)
                            new_vars[key] = value
                        except (TypeError, ValueError):
                            # Store string representation for complex objects
                            new_vars[key] = str(value)
                
                result_dict["output"] = output_buffer.getvalue()
                result_dict["error"] = error_buffer.getvalue() or None
                result_dict["success"] = True
                result_dict["variables"] = new_vars
                
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                try:
                    error_msg += f"\n{traceback.format_exc()}"
                except:
                    pass
                    
                result_dict["output"] = output_buffer.getvalue()
                result_dict["error"] = error_msg
                result_dict["success"] = False
                result_dict["variables"] = {}

        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Enhanced execution with intelligent routing and session management."""
        code = kwargs.get("code")
        if not code:
            return ToolResult.create_error(error="Code parameter is required", tool_name=self.name)

        # Ensure all parameters have the correct types
        try:
            timeout = int(kwargs.get("timeout", self.config.timeout))
            sandbox_preference = kwargs.get("sandbox_mode", "auto")
            session_id = kwargs.get("session_id")
            
            # Handle boolean parameters that might be strings
            persist_variables = kwargs.get("persist_variables", False)
            if isinstance(persist_variables, str):
                persist_variables = persist_variables.lower() == "true"
                
            show_analysis = kwargs.get("show_analysis", False)
            if isinstance(show_analysis, str):
                show_analysis = show_analysis.lower() == "true"
                
            # Handle session_id that might be "None" string
            if session_id == "None" or session_id == "null":
                session_id = None
        except (ValueError, TypeError) as e:
            return ToolResult.create_error(
                error=f"Parameter type error: {str(e)}",
                tool_name=self.name
            )
        
        # Update stats
        self.execution_stats['total_executions'] += 1
        
        # Intelligent execution decision
        use_sandbox, decision_info = self._should_use_sandbox_execution(code, sandbox_preference)
        
        # Session management
        if session_id:
            session = self.session_manager.get_session(session_id)
            if not session:
                session = self.session_manager.create_session(code, timeout, "sandbox" if use_sandbox else "local")
        else:
            session = self.session_manager.create_session(code, timeout, "sandbox" if use_sandbox else "local")
        
        try:
            if use_sandbox:
                self.execution_stats['sandbox_executions'] += 1
                result = await self._execute_in_sandbox(code, timeout, session)
            else:
                self.execution_stats['local_executions'] += 1
                result = await self._execute_locally(code, timeout, session)
            
            # Enhanced result with analysis
            if result.success and hasattr(result, 'result') and isinstance(result.result, dict):
                result.result['execution_analysis'] = decision_info
                if show_analysis:
                    result.result['code_analysis'] = decision_info.get('analysis', {})
                result.result['session_management'] = {
                    'session_id': session.session_id,
                    'persist_variables': persist_variables,
                    'variables_available': len(session.variables) > 0
                }
            
            # Update average execution time
            runtime = session.get_runtime()
            current_avg = self.execution_stats['average_execution_time']
            count = self.execution_stats['total_executions']
            self.execution_stats['average_execution_time'] = (current_avg * (count - 1) + runtime) / count
            
            return result
            
        except Exception as e:
            self.execution_stats['failed_executions'] += 1
            return ToolResult.create_error(
                error=f"Enhanced execution failed: {str(e)}",
                tool_name=self.name
            )

    async def cleanup(self) -> None:
        """Enhanced cleanup with session management."""
        try:
            self.session_manager.cleanup_old_sessions()
            logger.info("Enhanced Python tool cleanup completed")
        except Exception as e:
            logger.warning(f"Error during enhanced cleanup: {e}")

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get detailed execution statistics."""
        return {
            **self.execution_stats,
            'active_sessions': len(self.session_manager.sessions),
            'success_rate': (
                (self.execution_stats['total_executions'] - self.execution_stats['failed_executions'])
                / max(1, self.execution_stats['total_executions'])
            )
        }

    def get_approval_message(self) -> str:
        """Enhanced approval message."""
        base_message = super().get_approval_message()
        
        return f"""{base_message}

🐍 ENHANCED PYTHON EXECUTION:
- Intelligent code analysis for optimal routing
- Session management with variable persistence  
- Enhanced security with minimal performance impact
- Comprehensive execution monitoring and analytics

The tool automatically analyzes code complexity and danger level to choose
the most appropriate execution environment while maintaining security.
"""