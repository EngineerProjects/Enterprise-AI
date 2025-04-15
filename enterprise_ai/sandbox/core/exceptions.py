"""Exception classes for the sandbox system."""

from enterprise_ai.exceptions import EnterpriseAIError


class SandboxError(EnterpriseAIError):
    """Base exception for sandbox-related errors."""

    def __init__(self, message: str = "An error occurred in the sandbox") -> None:
        super().__init__(message)


class SandboxTimeoutError(SandboxError):
    """Exception raised when a sandbox operation times out."""

    def __init__(self, message: str = "Sandbox operation timed out") -> None:
        super().__init__(message)


class SandboxResourceError(SandboxError):
    """Exception raised for resource-related errors."""

    def __init__(self, message: str = "Sandbox resource error") -> None:
        super().__init__(message)
