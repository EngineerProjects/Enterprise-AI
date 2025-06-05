"""
Configuration management tool for Enterprise AI.

This tool provides interface to the configuration management system,
allowing users to view, modify, and manage system configuration.
"""

from typing import Any, Dict, List, Optional, Set, Union

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.tool.core.config_manager import get_config_manager, ConfigManager
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.core.config_tool")


@register_tool(category="core", capabilities=["system_config", "configuration"])
class ConfigurationTool(BaseTool):
    """
    Configuration management tool for Enterprise AI system configuration.

    Key capabilities:
    * View current system configuration and individual values
    * Update configuration values with validation and type checking
    * Reset configuration to defaults with backup creation
    * Import and export configuration files for backup and sharing
    * View configuration change history and audit trail
    * Validate paths and commands against security policies
    * Manage allowed directories and blocked commands for security
    * Control system behavior through configuration parameters

    Use this tool when:
    * You need to view or modify system configuration settings
    * You want to configure security policies and access controls
    * You need to backup or restore configuration settings
    * You want to see what configuration changes have been made
    * You need to validate paths or commands against current policies
    * You want to control tool behavior through configuration

    Configuration Categories:
    * Security: allowedDirectories, blockedCommands, enableSandboxMode
    * Performance: fileReadLineLimit, fileWriteLineLimit, maxSessionTimeout
    * Behavior: defaultShell, fuzzySearchThreshold, telemetryEnabled
    * System: logLevel, autoBackup, maxBackupFiles
    """

    name: str = "configuration"
    description: str = """
    Configuration management tool for Enterprise AI system settings and policies.

    * Purpose: Manage system configuration, security policies, and behavioral settings
    * Usage: View, update, backup, restore configuration with validation
    * Features: Type validation, change history, security controls, backup management
    * Returns: Configuration data, update confirmations, validation results, and change logs

    Provides centralized access to system configuration with proper validation,
    security controls, and audit capabilities. Supports both individual setting
    updates and bulk configuration operations with automatic backup creation.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "description": "Configuration action to perform",
                "enum": [
                    "get_config", "get_value", "set_value", "update_config",
                    "reset_defaults", "reload_file", "get_history",
                    "export_config", "import_config", "validate_path",
                    "check_command", "list_allowed_dirs", "list_blocked_commands"
                ],
                "type": "string",
            },
            "key": {"description": "Configuration key for get_value/set_value actions", "type": "string"},
            "value": {"description": "Value to set for set_value action", "type": ["string", "number", "boolean", "array", "object"]},
            "config_updates": {"description": "Dictionary of key-value pairs for update_config", "type": "object"},
            "file_path": {"description": "File path for import/export operations", "type": "string"},
            "path_to_validate": {"description": "Path to validate against allowed directories", "type": "string"},
            "command_to_check": {"description": "Command to check against blocked commands", "type": "string"},
            "merge": {"description": "Whether to merge on import (true) or replace (false)", "type": "boolean"},
            "include_sensitive": {"description": "Include sensitive configuration values", "type": "boolean"},
        },
        "required": ["action"],
    }

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.SYSTEM_CONFIG}
    requires_initialization: bool = False

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None, 
                 parameters: Optional[dict] = None, config: Optional[ToolConfig] = None, **kwargs: Any) -> None:
        """Initialize the ConfigurationTool."""
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            **kwargs,
        )

        self.config = config or ToolConfig(timeout=30.0, max_retries=1)
        logger.debug("ConfigurationTool initialized")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a configuration management action."""
        action = kwargs.get("action")
        
        if not action:
            raise ToolError("Parameter 'action' is required")

        logger.info(f"Executing configuration action: {action}")

        try:
            config_manager = await get_config_manager()
            
            if action == "get_config":
                return await self._get_config(config_manager, kwargs)
            elif action == "get_value":
                return await self._get_value(config_manager, kwargs)
            elif action == "set_value":
                return await self._set_value(config_manager, kwargs)
            elif action == "update_config":
                return await self._update_config(config_manager, kwargs)
            elif action == "reset_defaults":
                return await self._reset_defaults(config_manager, kwargs)
            elif action == "reload_file":
                return await self._reload_file(config_manager, kwargs)
            elif action == "get_history":
                return await self._get_history(config_manager, kwargs)
            elif action == "export_config":
                return await self._export_config(config_manager, kwargs)
            elif action == "import_config":
                return await self._import_config(config_manager, kwargs)
            elif action == "validate_path":
                return await self._validate_path(config_manager, kwargs)
            elif action == "check_command":
                return await self._check_command(config_manager, kwargs)
            elif action == "list_allowed_dirs":
                return await self._list_allowed_dirs(config_manager, kwargs)
            elif action == "list_blocked_commands":
                return await self._list_blocked_commands(config_manager, kwargs)
            else:
                raise ToolError(f"Unsupported action: {action}")
                
        except ToolError as e:
            return ToolResult.create_error(error=str(e), tool_name=self.name)
        except Exception as e:
            return ToolResult.create_error(error=f"Error executing action {action}: {str(e)}", tool_name=self.name)

    async def _get_config(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Get full configuration."""
        include_sensitive = kwargs.get("include_sensitive", False)
        
        config = await config_manager.get_config()
        
        # Filter sensitive information if requested
        if not include_sensitive:
            sensitive_keys = ["telemetryEnabled"]  # Add more as needed
            filtered_config = {k: v for k, v in config.items() if k not in sensitive_keys}
        else:
            filtered_config = config
        
        # Format output nicely
        output = "Current Enterprise AI Configuration:\n\n"
        
        categories = {
            "Security Settings": ["allowedDirectories", "blockedCommands", "enableSandboxMode"],
            "Performance Settings": ["fileReadLineLimit", "fileWriteLineLimit", "maxSessionTimeout"],
            "Behavior Settings": ["defaultShell", "fuzzySearchThreshold", "telemetryEnabled"],
            "System Settings": ["logLevel", "autoBackup", "maxBackupFiles", "version", "lastUpdated"]
        }
        
        for category, keys in categories.items():
            output += f"## {category}\n"
            for key in keys:
                if key in filtered_config:
                    value = filtered_config[key]
                    if isinstance(value, list) and len(value) > 3:
                        # Truncate long lists
                        display_value = f"[{len(value)} items] {value[:3]}..."
                    else:
                        display_value = value
                    output += f"  {key}: {display_value}\n"
            output += "\n"
        
        # Add any uncategorized settings
        categorized_keys = set()
        for keys in categories.values():
            categorized_keys.update(keys)
        
        uncategorized = {k: v for k, v in filtered_config.items() if k not in categorized_keys}
        if uncategorized:
            output += "## Other Settings\n"
            for key, value in uncategorized.items():
                output += f"  {key}: {value}\n"
        
        return CLIResult.create_success(result=output, tool_name=self.name)

    async def _get_value(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Get specific configuration value."""
        key = kwargs.get("key")
        if not key:
            raise ToolError("Parameter 'key' is required for get_value action")
        
        value = await config_manager.get_value(key)
        
        if value is None:
            result = f"Configuration key '{key}' not found or is None"
        else:
            result = f"Configuration value for '{key}':\n{value}"
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _set_value(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Set specific configuration value."""
        key = kwargs.get("key")
        value = kwargs.get("value")
        
        if not key:
            raise ToolError("Parameter 'key' is required for set_value action")
        if value is None:
            raise ToolError("Parameter 'value' is required for set_value action")
        
        old_value = await config_manager.get_value(key)
        success = await config_manager.set_value(key, value)
        
        if success:
            result = f"Successfully updated configuration:\n"
            result += f"  Key: {key}\n"
            result += f"  Old Value: {old_value}\n"
            result += f"  New Value: {value}"
        else:
            result = f"Failed to update configuration key '{key}'. Value may be invalid."
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _update_config(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Update multiple configuration values."""
        config_updates = kwargs.get("config_updates")
        if not config_updates:
            raise ToolError("Parameter 'config_updates' is required for update_config action")
        
        if not isinstance(config_updates, dict):
            raise ToolError("Parameter 'config_updates' must be a dictionary")
        
        results = await config_manager.update_config(config_updates)
        
        output = "Configuration update results:\n\n"
        successful_updates = []
        failed_updates = []
        
        for key, success in results.items():
            if success:
                successful_updates.append(key)
                output += f"✓ {key}: Updated successfully\n"
            else:
                failed_updates.append(key)
                output += f"✗ {key}: Update failed (validation error)\n"
        
        output += f"\nSummary: {len(successful_updates)} successful, {len(failed_updates)} failed"
        
        return CLIResult.create_success(result=output, tool_name=self.name)

    async def _reset_defaults(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Reset configuration to defaults."""
        await config_manager.reset_to_defaults()
        
        result = "Configuration has been reset to default values.\n"
        result += "All previous settings have been backed up and can be restored if needed."
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _reload_file(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Reload configuration from file."""
        success = await config_manager.reload_from_file()
        
        if success:
            result = "Configuration successfully reloaded from file."
        else:
            result = "Failed to reload configuration from file. Check file permissions and format."
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _get_history(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Get configuration change history."""
        history = config_manager.get_change_history()
        
        if not history:
            result = "No configuration changes recorded."
        else:
            result = "Configuration Change History:\n\n"
            for i, change in enumerate(reversed(history), 1):  # Most recent first
                result += f"{i}. {change['timestamp']}\n"
                result += f"   Key: {change['key']}\n"
                result += f"   Old Value: {change['old_value']}\n"
                result += f"   New Value: {change['new_value']}\n\n"
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _export_config(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Export configuration to file."""
        file_path = kwargs.get("file_path")
        if not file_path:
            raise ToolError("Parameter 'file_path' is required for export_config action")
        
        success = await config_manager.export_config(file_path)
        
        if success:
            result = f"Configuration successfully exported to: {file_path}"
        else:
            result = f"Failed to export configuration to: {file_path}"
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _import_config(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Import configuration from file."""
        file_path = kwargs.get("file_path")
        merge = kwargs.get("merge", True)
        
        if not file_path:
            raise ToolError("Parameter 'file_path' is required for import_config action")
        
        success = await config_manager.import_config(file_path, merge)
        
        if success:
            mode = "merged with" if merge else "replaced"
            result = f"Configuration successfully imported from {file_path} and {mode} current settings."
        else:
            result = f"Failed to import configuration from: {file_path}"
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _validate_path(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Validate if path is allowed."""
        path_to_validate = kwargs.get("path_to_validate")
        if not path_to_validate:
            raise ToolError("Parameter 'path_to_validate' is required for validate_path action")
        
        is_allowed = await config_manager.validate_path(path_to_validate)
        
        result = f"Path validation for: {path_to_validate}\n"
        result += f"Status: {'ALLOWED' if is_allowed else 'BLOCKED'}\n"
        
        if not is_allowed:
            allowed_dirs = await config_manager.get_value("allowedDirectories", [])
            if allowed_dirs:
                result += f"Allowed directories: {allowed_dirs}"
            else:
                result += "No directory restrictions configured (full access enabled)"
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _check_command(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """Check if command is blocked."""
        command_to_check = kwargs.get("command_to_check")
        if not command_to_check:
            raise ToolError("Parameter 'command_to_check' is required for check_command action")
        
        is_blocked = await config_manager.is_command_blocked(command_to_check)
        
        result = f"Command check for: {command_to_check}\n"
        result += f"Status: {'BLOCKED' if is_blocked else 'ALLOWED'}\n"
        
        if is_blocked:
            blocked_commands = await config_manager.get_value("blockedCommands", [])
            result += f"Blocked command patterns: {blocked_commands}"
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _list_allowed_dirs(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """List allowed directories."""
        allowed_dirs = await config_manager.get_value("allowedDirectories", [])
        
        if not allowed_dirs:
            result = "No directory restrictions configured.\nFull filesystem access is enabled."
        else:
            result = f"Allowed directories ({len(allowed_dirs)}):\n"
            for i, directory in enumerate(allowed_dirs, 1):
                result += f"  {i}. {directory}\n"
        
        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _list_blocked_commands(self, config_manager: ConfigManager, kwargs: dict) -> CLIResult:
        """List blocked commands."""
        blocked_commands = await config_manager.get_value("blockedCommands", [])
        
        if not blocked_commands:
            result = "No command restrictions configured.\nAll commands are allowed."
        else:
            result = f"Blocked command patterns ({len(blocked_commands)}):\n"
            for i, command in enumerate(blocked_commands, 1):
                result += f"  {i}. {command}\n"
        
        return CLIResult.create_success(result=result, tool_name=self.name)