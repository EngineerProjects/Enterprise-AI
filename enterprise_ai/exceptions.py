"""
Custom exception classes for Enterprise AI.

This module provides a detailed hierarchy of exception types for different error scenarios
in the Enterprise AI framework, enabling precise error handling and reporting
throughout the system. Each exception class includes helpful error messages and
contextual information to simplify debugging and error recovery.
"""

from typing import Any, Dict, List, Optional, Union


class EnterpriseAIError(Exception):
    """Base exception for all Enterprise AI errors.

    All other exceptions in the framework should inherit from this base class to
    enable catch-all error handling when needed.
    """

    def __init__(self, message: str = "An error occurred in Enterprise AI") -> None:
        self.message = message
        super().__init__(self.message)


# -----------------------------------------------------------------------------
# Configuration Errors
# -----------------------------------------------------------------------------


class ConfigError(EnterpriseAIError):
    """Base class for configuration-related errors.

    This class serves as the parent for all configuration issues, including
    file loading problems, validation errors, and missing configuration data.
    """

    def __init__(self, message: str = "Error in Enterprise AI configuration") -> None:
        super().__init__(message)


class ConfigFileError(ConfigError):
    """Error loading or parsing configuration files.

    Raised when there's an issue with reading, parsing, or accessing
    configuration files.
    """

    def __init__(self, file_path: Optional[str] = None, message: Optional[str] = None) -> None:
        self.file_path = file_path
        msg = message or f"Error loading configuration file: {file_path}"
        super().__init__(msg)


class ConfigValueError(ConfigError):
    """Error with configuration values.

    Raised when configuration values are invalid, missing, or incompatible.
    """

    def __init__(
        self, key: Optional[str] = None, value: Optional[Any] = None, message: Optional[str] = None
    ) -> None:
        self.key = key
        self.value = value
        msg = message or f"Invalid configuration value for {key}: {value}"
        super().__init__(msg)


class ConfigValidationError(ConfigError):
    """Error validating configuration structure or relationships.

    Raised when configuration passes basic value checking but fails higher-level
    validation rules or constraints.
    """

    def __init__(self, section: Optional[str] = None, message: Optional[str] = None) -> None:
        self.section = section
        section_info = f" in section '{section}'" if section else ""
        msg = message or f"Configuration validation error{section_info}"
        super().__init__(msg)


class ConfigDependencyError(ConfigError):
    """Error with configuration dependencies.

    Raised when there's an issue with interdependent configuration options.
    """

    def __init__(
        self,
        dependency: Optional[str] = None,
        dependent: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.dependency = dependency
        self.dependent = dependent
        dep_info = f"'{dependent}' depends on '{dependency}'" if dependent and dependency else ""
        msg = message or f"Configuration dependency error: {dep_info}"
        super().__init__(msg)


# -----------------------------------------------------------------------------
# LLM Errors
# -----------------------------------------------------------------------------


class LLMError(EnterpriseAIError):
    """Base class for LLM-related errors.

    Serves as the parent class for all errors related to language model
    operations, including API issues, token limitations, and model availability.
    """

    def __init__(self, message: str = "Error in LLM operation") -> None:
        super().__init__(message)


class TokenLimitExceeded(LLMError):
    """Exception raised when the token limit is exceeded.

    Occurs when an operation would require more tokens than the model supports.
    """

    def __init__(self, model: Optional[str] = None, message: Optional[str] = None) -> None:
        self.model = model
        model_info = f" for model {model}" if model else ""
        msg = message or f"Token limit exceeded{model_info}"
        super().__init__(msg)


class ModelNotAvailable(LLMError):
    """Exception raised when a requested LLM model is not available.

    This can happen due to API limitations, subscription level, or because
    the model name is incorrect.
    """

    def __init__(self, model_name: Optional[str] = None, message: Optional[str] = None) -> None:
        self.model_name = model_name
        msg = message or f"Model not available: {model_name}"
        super().__init__(msg)


class ProviderNotSupportedError(LLMError):
    """Exception raised when a requested provider is not supported.

    Raised when trying to use an LLM provider that is not implemented or configured.
    """

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Provider not supported: {provider}")


class ModelCapabilityError(LLMError):
    """Exception raised when a model doesn't support a requested capability.

    This occurs when attempting to use features like vision, function calling,
    or other capabilities not supported by the specified model.
    """

    def __init__(self, model: str, capability: str) -> None:
        self.model = model
        self.capability = capability
        super().__init__(f"Model {model} does not support capability: {capability}")


class ContextWindowExceededError(TokenLimitExceeded):
    """Exception raised when the context window size is exceeded.

    More specific version of TokenLimitExceeded that includes information about
    the current token count and maximum allowed.
    """

    def __init__(self, model: str, token_count: int, max_tokens: int) -> None:
        self.model = model
        self.token_count = token_count
        self.max_tokens = max_tokens
        super().__init__(
            model, f"Context window exceeded for {model}: {token_count} tokens (max: {max_tokens})"
        )


class APIError(LLMError):
    """Exception raised when an API error occurs.

    General error for API-related issues such as network problems, rate limiting,
    or server errors.
    """

    def __init__(self, status_code: Optional[int] = None, message: Optional[str] = None) -> None:
        self.status_code = status_code
        status_info = f" (status {status_code})" if status_code else ""
        msg = message or f"API error occurred{status_info}"
        super().__init__(msg)


class TokenCountError(LLMError):
    """Exception raised when there's an error counting tokens.

    Occurs when token counting fails due to unsupported models or other issues.
    """

    def __init__(self, message: str = "Error counting tokens", model: Optional[str] = None) -> None:
        self.model = model
        msg = f"{message} for model {model}" if model else message
        super().__init__(msg)


class ParameterError(LLMError):
    """Exception raised when there's an error with request parameters.

    Raised when parameters provided to an LLM request are invalid.
    """

    def __init__(self, message: str, parameter: Optional[str] = None) -> None:
        self.parameter = parameter
        param_info = f" for {parameter}" if parameter else ""
        msg = f"Parameter error{param_info}: {message}"
        super().__init__(msg)


class ImageProcessingError(LLMError):
    """Exception raised when there's an error processing images.

    Occurs during image encoding, decoding, or format conversion for vision models.
    """

    def __init__(self, message: str, source: Optional[str] = None) -> None:
        self.source = source
        source_info = f" for {source}" if source else ""
        msg = f"Image processing error{source_info}: {message}"
        super().__init__(msg)


# -----------------------------------------------------------------------------
# Tool Errors
# -----------------------------------------------------------------------------


class ToolError(EnterpriseAIError):
    """Base class for tool-related errors.

    Parent class for all errors related to tool execution, permissions,
    and availability.
    """

    def __init__(self, message: str = "Error in tool execution") -> None:
        super().__init__(message)


class ToolNotFound(ToolError):
    """Exception raised when a requested tool is not found.

    Occurs when an agent attempts to use a tool that doesn't exist or isn't registered.
    """

    def __init__(self, tool_name: Optional[str] = None, message: Optional[str] = None) -> None:
        self.tool_name = tool_name
        msg = message or f"Tool not found: {tool_name}"
        super().__init__(msg)


class ToolExecutionError(ToolError):
    """Exception raised when a tool execution fails.

    General error for any issue that occurs during tool execution.
    """

    def __init__(
        self,
        tool_name: Optional[str] = None,
        error: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self.tool_name = tool_name
        self.error = error
        msg = message or f"Error executing tool {tool_name}: {error}"
        super().__init__(msg)


class ToolPermissionError(ToolError):
    """Exception raised when a tool permission error occurs.

    Raised when an agent attempts to use a tool it doesn't have permission to access.
    """

    def __init__(
        self,
        tool_name: Optional[str] = None,
        agent_name: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.tool_name = tool_name
        self.agent_name = agent_name
        msg = message or f"Permission denied for {agent_name} to use tool {tool_name}"
        super().__init__(msg)


class ToolInputError(ToolError):
    """Exception raised when tool input validation fails.

    Occurs when the input provided to a tool is invalid or incomplete.
    """

    def __init__(
        self,
        tool_name: Optional[str] = None,
        input_data: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self.tool_name = tool_name
        self.input_data = input_data
        msg = message or f"Invalid input for tool {tool_name}"
        super().__init__(msg)


class ToolTimeoutError(ToolError):
    """Exception raised when a tool execution times out.

    Occurs when a tool takes too long to execute and exceeds its timeout limit.
    """

    def __init__(
        self,
        tool_name: Optional[str] = None,
        timeout: Optional[float] = None,
        message: Optional[str] = None,
    ) -> None:
        self.tool_name = tool_name
        self.timeout = timeout
        timeout_info = f" after {timeout} seconds" if timeout is not None else ""
        msg = message or f"Tool {tool_name} execution timed out{timeout_info}"
        super().__init__(msg)


# -----------------------------------------------------------------------------
# Agent Errors
# -----------------------------------------------------------------------------


class AgentError(EnterpriseAIError):
    """Base class for agent-related errors.

    Parent class for all errors related to agent initialization, execution,
    and state management.
    """

    def __init__(self, message: str = "Error in agent operation") -> None:
        super().__init__(message)


class AgentNotFound(AgentError):
    """Exception raised when a requested agent is not found.

    Occurs when attempting to access an agent that doesn't exist.
    """

    def __init__(self, agent_name: Optional[str] = None, message: Optional[str] = None) -> None:
        self.agent_name = agent_name
        msg = message or f"Agent not found: {agent_name}"
        super().__init__(msg)


class AgentExecutionError(AgentError):
    """Exception raised when an agent execution fails.

    General error for any issue during agent execution that isn't covered
    by more specific exceptions.
    """

    def __init__(
        self,
        agent_name: Optional[str] = None,
        error: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self.agent_name = agent_name
        self.error = error
        msg = message or f"Error executing agent {agent_name}: {error}"
        super().__init__(msg)


class AgentStateError(AgentError):
    """Exception raised when an agent is in an invalid state for an operation.

    Occurs when attempting an operation that isn't valid for the agent's current state.
    """

    def __init__(
        self,
        agent_name: Optional[str] = None,
        current_state: Optional[str] = None,
        required_state: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.agent_name = agent_name
        self.current_state = current_state
        self.required_state = required_state
        msg = (
            message or f"Agent {agent_name} in state {current_state}, but requires {required_state}"
        )
        super().__init__(msg)


class AgentConfigurationError(AgentError):
    """Exception raised when there's an issue with agent configuration.

    Occurs during agent initialization when configuration is invalid or incomplete.
    """

    def __init__(
        self,
        agent_name: Optional[str] = None,
        config_error: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.agent_name = agent_name
        self.config_error = config_error
        msg = message or f"Configuration error for agent {agent_name}: {config_error}"
        super().__init__(msg)


class AgentCommunicationError(AgentError):
    """Exception raised when inter-agent communication fails.

    Occurs when agents cannot successfully communicate with each other.
    """

    def __init__(
        self,
        sender: Optional[str] = None,
        receiver: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.sender = sender
        self.receiver = receiver
        msg = message or f"Communication error between agents {sender} and {receiver}"
        super().__init__(msg)


# -----------------------------------------------------------------------------
# Team Errors
# -----------------------------------------------------------------------------


class TeamError(EnterpriseAIError):
    """Base class for team-related errors.

    Parent class for all errors related to team creation, management,
    and operations.
    """

    def __init__(self, message: str = "Error in team operation") -> None:
        super().__init__(message)


class TeamNotFound(TeamError):
    """Exception raised when a requested team is not found.

    Occurs when attempting to access a team that doesn't exist.
    """

    def __init__(self, team_name: Optional[str] = None, message: Optional[str] = None) -> None:
        self.team_name = team_name
        msg = message or f"Team not found: {team_name}"
        super().__init__(msg)


class TeamConfigError(TeamError):
    """Exception raised when a team configuration error occurs.

    Occurs during team initialization or reconfiguration.
    """

    def __init__(
        self,
        team_name: Optional[str] = None,
        error: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self.team_name = team_name
        self.error = error
        msg = message or f"Team configuration error for {team_name}: {error}"
        super().__init__(msg)


class TeamSizeError(TeamError):
    """Exception raised when a team size constraint is violated.

    Occurs when attempting to add too many members to a team.
    """

    def __init__(
        self,
        team_name: Optional[str] = None,
        current_size: Optional[int] = None,
        max_size: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        self.team_name = team_name
        self.current_size = current_size
        self.max_size = max_size
        msg = message or f"Team {team_name} size ({current_size}) exceeds maximum ({max_size})"
        super().__init__(msg)


class TeamRoleError(TeamError):
    """Exception raised when there's an issue with team roles.

    Occurs when team roles are invalid, duplicated, or missing required roles.
    """

    def __init__(
        self,
        team_name: Optional[str] = None,
        role: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.team_name = team_name
        self.role = role
        role_info = f" for role '{role}'" if role else ""
        msg = message or f"Team {team_name} has a role configuration issue{role_info}"
        super().__init__(msg)


class TeamStateError(TeamError):
    """Exception raised when a team is in an invalid state for an operation.

    Occurs when attempting an operation that isn't valid for the team's current state.
    """

    def __init__(
        self,
        team_name: Optional[str] = None,
        current_state: Optional[str] = None,
        required_state: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.team_name = team_name
        self.current_state = current_state
        self.required_state = required_state
        msg = message or f"Team {team_name} in state {current_state}, but requires {required_state}"
        super().__init__(msg)


# -----------------------------------------------------------------------------
# Task Errors
# -----------------------------------------------------------------------------


class TaskError(EnterpriseAIError):
    """Base class for task-related errors.

    Parent class for all errors related to task creation, assignment,
    and execution.
    """

    def __init__(self, message: str = "Error in task operation") -> None:
        super().__init__(message)


class TaskNotFound(TaskError):
    """Exception raised when a requested task is not found.

    Occurs when attempting to access a task that doesn't exist.
    """

    def __init__(self, task_id: Optional[str] = None, message: Optional[str] = None) -> None:
        self.task_id = task_id
        msg = message or f"Task not found: {task_id}"
        super().__init__(msg)


class TaskStateError(TaskError):
    """Exception raised when a task is in an invalid state for an operation.

    Occurs when attempting an operation that isn't valid for the task's current state.
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        current_state: Optional[str] = None,
        required_state: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.task_id = task_id
        self.current_state = current_state
        self.required_state = required_state
        msg = message or f"Task {task_id} in state {current_state}, but requires {required_state}"
        super().__init__(msg)


class TaskDependencyError(TaskError):
    """Exception raised when a task dependency constraint is violated.

    Occurs when attempting to execute a task whose dependencies aren't satisfied.
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.task_id = task_id
        self.dependency_id = dependency_id
        msg = message or f"Task {task_id} depends on incomplete task {dependency_id}"
        super().__init__(msg)


class TaskAssignmentError(TaskError):
    """Exception raised when there's an issue with task assignment.

    Occurs when a task cannot be properly assigned to an agent or team.
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        assignee: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.task_id = task_id
        self.assignee = assignee
        msg = message or f"Cannot assign task {task_id} to {assignee}"
        super().__init__(msg)


# -----------------------------------------------------------------------------
# Workflow Errors
# -----------------------------------------------------------------------------


class WorkflowError(EnterpriseAIError):
    """Base class for workflow-related errors.

    Parent class for all errors related to workflow definition, execution,
    and monitoring.
    """

    def __init__(self, message: str = "Error in workflow operation") -> None:
        super().__init__(message)


class WorkflowNotFound(WorkflowError):
    """Exception raised when a requested workflow is not found.

    Occurs when attempting to access a workflow that doesn't exist.
    """

    def __init__(self, workflow_id: Optional[str] = None, message: Optional[str] = None) -> None:
        self.workflow_id = workflow_id
        msg = message or f"Workflow not found: {workflow_id}"
        super().__init__(msg)


class WorkflowExecutionError(WorkflowError):
    """Exception raised when a workflow execution fails.

    General error for issues during workflow execution.
    """

    def __init__(
        self,
        workflow_id: Optional[str] = None,
        error: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.error = error
        msg = message or f"Error executing workflow {workflow_id}: {error}"
        super().__init__(msg)


class WorkflowValidationError(WorkflowError):
    """Exception raised when a workflow definition is invalid.

    Occurs during workflow validation when the definition has errors.
    """

    def __init__(
        self,
        workflow_id: Optional[str] = None,
        validation_error: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.validation_error = validation_error
        msg = message or f"Workflow {workflow_id} validation error: {validation_error}"
        super().__init__(msg)


class WorkflowStateError(WorkflowError):
    """Exception raised when a workflow is in an invalid state for an operation.

    Occurs when attempting an operation that isn't valid for the workflow's current state.
    """

    def __init__(
        self,
        workflow_id: Optional[str] = None,
        current_state: Optional[str] = None,
        required_state: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.current_state = current_state
        self.required_state = required_state
        msg = (
            message
            or f"Workflow {workflow_id} in state {current_state}, but requires {required_state}"
        )
        super().__init__(msg)


# -----------------------------------------------------------------------------
# Sandbox Errors
# -----------------------------------------------------------------------------


class SandboxError(EnterpriseAIError):
    """Base class for sandbox-related errors.

    Parent class for all errors related to execution sandboxes for
    code and command execution.
    """

    def __init__(self, message: str = "Error in sandbox operation") -> None:
        super().__init__(message)


class SandboxTimeoutError(SandboxError):
    """Exception raised when a sandbox operation times out.

    Occurs when an operation in the sandbox exceeds its time limit.
    """

    def __init__(self, timeout: Optional[int] = None, message: Optional[str] = None) -> None:
        self.timeout = timeout
        timeout_info = f" after {timeout} seconds" if timeout is not None else ""
        msg = message or f"Sandbox operation timed out{timeout_info}"
        super().__init__(msg)


class SandboxResourceError(SandboxError):
    """Exception raised when sandbox resource limits are exceeded.

    Occurs when an operation attempts to use more resources than allowed
    (memory, CPU, etc.).
    """

    def __init__(
        self,
        resource: Optional[str] = None,
        limit: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self.resource = resource
        self.limit = limit
        msg = message or f"Sandbox {resource} limit exceeded: {limit}"
        super().__init__(msg)


class SandboxInitializationError(SandboxError):
    """Exception raised when a sandbox fails to initialize.

    Occurs during sandbox creation or configuration.
    """

    def __init__(self, message: Optional[str] = None) -> None:
        msg = message or "Failed to initialize sandbox environment"
        super().__init__(msg)


class SandboxExecutionError(SandboxError):
    """Exception raised when execution within a sandbox fails.

    General error for issues during code or command execution in a sandbox.
    """

    def __init__(
        self,
        command: Optional[str] = None,
        return_code: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        self.command = command
        self.return_code = return_code
        cmd_info = f" executing '{command}'" if command else ""
        code_info = f" (return code: {return_code})" if return_code is not None else ""
        msg = message or f"Sandbox execution failed{cmd_info}{code_info}"
        super().__init__(msg)


# -----------------------------------------------------------------------------
# Security Errors
# -----------------------------------------------------------------------------


class SecurityError(EnterpriseAIError):
    """Base class for security-related errors.

    Parent class for all errors related to authorization, permissions,
    and security validation.
    """

    def __init__(self, message: str = "Security error") -> None:
        super().__init__(message)


class AuthorizationError(SecurityError):
    """Exception raised when an authorization error occurs.

    Occurs when an entity attempts an operation without proper authorization.
    """

    def __init__(
        self,
        entity: Optional[str] = None,
        action: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.entity = entity
        self.action = action
        msg = message or f"Authorization error: {entity} not authorized for {action}"
        super().__init__(msg)


class UnsafeOperationError(SecurityError):
    """Exception raised when an unsafe operation is attempted.

    Occurs when an operation is blocked for security reasons.
    """

    def __init__(
        self,
        operation: Optional[str] = None,
        reason: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.operation = operation
        self.reason = reason
        msg = message or f"Unsafe operation {operation}: {reason}"
        super().__init__(msg)


class AuthenticationError(SecurityError):
    """Exception raised when authentication fails.

    Occurs during failed login attempts or invalid credential usage.
    """

    def __init__(self, identity: Optional[str] = None, message: Optional[str] = None) -> None:
        self.identity = identity
        identity_info = f" for {identity}" if identity else ""
        msg = message or f"Authentication failed{identity_info}"
        super().__init__(msg)


class DataValidationError(SecurityError):
    """Exception raised when input data fails security validation.

    Occurs when user input or external data fails security checks.
    """

    def __init__(self, field: Optional[str] = None, message: Optional[str] = None) -> None:
        self.field = field
        field_info = f" in field '{field}'" if field else ""
        msg = message or f"Security validation failed{field_info}"
        super().__init__(msg)


# -----------------------------------------------------------------------------
# File and I/O Errors
# -----------------------------------------------------------------------------


class FileOperationError(EnterpriseAIError):
    """Base class for file operation errors.

    Parent class for all errors related to file system operations.
    """

    def __init__(self, message: str = "Error in file operation") -> None:
        super().__init__(message)


class FileReadError(FileOperationError):
    """Exception raised when a file read operation fails.

    Occurs when a file cannot be read due to permissions, non-existence,
    or other issues.
    """

    def __init__(
        self, path: Optional[str] = None, error: Optional[Any] = None, message: Optional[str] = None
    ) -> None:
        self.path = path
        self.error = error
        msg = message or f"Error reading file {path}: {error}"
        super().__init__(msg)


class FileWriteError(FileOperationError):
    """Exception raised when a file write operation fails.

    Occurs when a file cannot be written due to permissions, disk space,
    or other issues.
    """

    def __init__(
        self, path: Optional[str] = None, error: Optional[Any] = None, message: Optional[str] = None
    ) -> None:
        self.path = path
        self.error = error
        msg = message or f"Error writing to file {path}: {error}"
        super().__init__(msg)


class FileNotFoundError(FileOperationError):
    """Exception raised when a file is not found.

    More specific version of FileReadError for file existence issues.
    """

    def __init__(self, path: Optional[str] = None, message: Optional[str] = None) -> None:
        self.path = path
        msg = message or f"File not found: {path}"
        super().__init__(msg)


class FilePermissionError(FileOperationError):
    """Exception raised when file permissions prevent an operation.

    Occurs when attempting to access a file without proper permissions.
    """

    def __init__(
        self,
        path: Optional[str] = None,
        operation: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.path = path
        self.operation = operation
        operation_info = f" for {operation}" if operation else ""
        msg = message or f"Permission denied{operation_info} on file {path}"
        super().__init__(msg)


class DirectoryOperationError(FileOperationError):
    """Exception raised when a directory operation fails.

    Specific to directory-related operations like creation or listing.
    """

    def __init__(
        self,
        path: Optional[str] = None,
        operation: Optional[str] = None,
        error: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self.path = path
        self.operation = operation
        self.error = error
        operation_info = f" during {operation}" if operation else ""
        msg = message or f"Directory operation failed{operation_info} on {path}: {error}"
        super().__init__(msg)
