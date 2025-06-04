"""
Configuration management system for Enterprise AI inspired by Desktop Commander.

This module provides centralized configuration management with file persistence,
validation, security controls, and runtime configuration updates.
"""

import json
import os
import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Set
from dataclasses import dataclass, asdict
from datetime import datetime

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.core.config_manager")


@dataclass
class ConfigValidationRule:
    """Configuration validation rule."""
    key: str
    required: bool = False
    type_check: Optional[type] = None
    allowed_values: Optional[List[Any]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    validator_func: Optional[callable] = None


class ConfigManager:
    """
    Centralized configuration management system like Desktop Commander.
    
    Features:
    * File-based configuration persistence with atomic updates
    * Runtime configuration updates with validation
    * Security controls with allowed directories and blocked commands
    * Configuration versioning and backup system
    * Validation rules and type checking
    * Default configuration management
    * Configuration change notifications and logging
    """
    
    _instance: Optional['ConfigManager'] = None
    _lock = asyncio.Lock()
    
    def __init__(self, config_path: Optional[str] = None, auto_save: bool = True):
        self.config_path = config_path or self._get_default_config_path()
        self.auto_save = auto_save
        self.config: Dict[str, Any] = {}
        self.config_history: List[Dict[str, Any]] = []
        self.max_history = 10
        self._file_lock = asyncio.Lock()
        self._change_callbacks: List[callable] = []
        
        # Initialize validation rules
        self._validation_rules = self._setup_validation_rules()
        
        # Load configuration
        self._load_config()
    
    @classmethod
    async def get_instance(cls, config_path: Optional[str] = None) -> 'ConfigManager':
        """Get singleton instance of ConfigManager."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config_path)
        return cls._instance
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path."""
        # Try to use user config directory, fallback to local
        try:
            if os.name == 'nt':  # Windows
                config_dir = os.path.expanduser("~/AppData/Local/Enterprise-AI")
            else:  # Unix-like
                config_dir = os.path.expanduser("~/.config/enterprise-ai")
            
            Path(config_dir).mkdir(parents=True, exist_ok=True)
            return str(Path(config_dir) / "config.json")
        except Exception:
            # Fallback to local directory
            return str(Path.cwd() / "enterprise_ai_config.json")
    
    def _setup_validation_rules(self) -> Dict[str, ConfigValidationRule]:
        """Setup configuration validation rules."""
        return {
            "allowedDirectories": ConfigValidationRule(
                key="allowedDirectories",
                type_check=list,
                validator_func=self._validate_directory_list
            ),
            "blockedCommands": ConfigValidationRule(
                key="blockedCommands", 
                type_check=list,
                validator_func=self._validate_command_list
            ),
            "fileReadLineLimit": ConfigValidationRule(
                key="fileReadLineLimit",
                type_check=int,
                min_value=1,
                max_value=100000
            ),
            "fileWriteLineLimit": ConfigValidationRule(
                key="fileWriteLineLimit",
                type_check=int,
                min_value=1,
                max_value=10000
            ),
            "telemetryEnabled": ConfigValidationRule(
                key="telemetryEnabled",
                type_check=bool
            ),
            "defaultShell": ConfigValidationRule(
                key="defaultShell",
                type_check=str,
                allowed_values=["bash", "sh", "zsh", "fish", "powershell", "cmd"]
            ),
            "maxSessionTimeout": ConfigValidationRule(
                key="maxSessionTimeout",
                type_check=int,
                min_value=1000,
                max_value=3600000  # 1 hour max
            ),
            "enableSandboxMode": ConfigValidationRule(
                key="enableSandboxMode",
                type_check=bool
            ),
            "logLevel": ConfigValidationRule(
                key="logLevel",
                type_check=str,
                allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            ),
            "fuzzySearchThreshold": ConfigValidationRule(
                key="fuzzySearchThreshold",
                type_check=float,
                min_value=0.0,
                max_value=1.0
            )
        }
    
    def _validate_directory_list(self, directories: List[str]) -> bool:
        """Validate directory list."""
        if not isinstance(directories, list):
            return False
        
        for directory in directories:
            if not isinstance(directory, str):
                return False
            # Basic path validation
            try:
                Path(directory).resolve()
            except Exception:
                return False
        
        return True
    
    def _validate_command_list(self, commands: List[str]) -> bool:
        """Validate blocked commands list."""
        if not isinstance(commands, list):
            return False
        
        for command in commands:
            if not isinstance(command, str) or not command.strip():
                return False
        
        return True
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "allowedDirectories": [],  # Empty array allows full access like Desktop Commander
            "blockedCommands": [
                "rm -rf /",
                "rm -rf /*", 
                "mkfs.",
                "fdisk",
                "dd if=/dev/zero",
                ":(){ :|:& };:",  # Fork bomb
                "chmod -R 777 /",
                "chown -R root /",
                "sudo rm -rf",
                "format c:"
            ],
            "fileReadLineLimit": 1000,
            "fileWriteLineLimit": 50,
            "telemetryEnabled": True,
            "defaultShell": "bash" if os.name != 'nt' else "powershell",
            "maxSessionTimeout": 300000,  # 5 minutes
            "enableSandboxMode": True,
            "logLevel": "INFO",
            "fuzzySearchThreshold": 0.7,
            "version": "1.0.0",
            "lastUpdated": datetime.now().isoformat(),
            "autoBackup": True,
            "maxBackupFiles": 5
        }
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                
                # Merge with defaults
                default_config = self._get_default_config()
                default_config.update(file_config)
                self.config = default_config
                
                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                # Use defaults and save
                self.config = self._get_default_config()
                self._save_config_sync()
                logger.info(f"Created default configuration at {self.config_path}")
                
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self.config = self._get_default_config()
    
    def _save_config_sync(self) -> None:
        """Save configuration synchronously."""
        try:
            # Create backup if auto backup is enabled
            if self.config.get("autoBackup", True):
                self._create_backup()
            
            # Update timestamp
            self.config["lastUpdated"] = datetime.now().isoformat()
            
            # Atomic write
            temp_path = f"{self.config_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            # Atomic move
            if os.name == 'nt':
                # Windows doesn't support atomic move if target exists
                if Path(self.config_path).exists():
                    os.remove(self.config_path)
            os.rename(temp_path, self.config_path)
            
            logger.debug(f"Configuration saved to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            # Clean up temp file
            try:
                if Path(temp_path).exists():
                    os.remove(temp_path)
            except:
                pass
    
    async def _save_config(self) -> None:
        """Save configuration asynchronously with file locking."""
        async with self._file_lock:
            await asyncio.get_event_loop().run_in_executor(None, self._save_config_sync)
    
    def _create_backup(self) -> None:
        """Create configuration backup."""
        try:
            if not Path(self.config_path).exists():
                return
            
            backup_dir = Path(self.config_path).parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"config_backup_{timestamp}.json"
            
            # Copy current config to backup
            import shutil
            shutil.copy2(self.config_path, backup_path)
            
            # Clean up old backups
            self._cleanup_old_backups(backup_dir)
            
            logger.debug(f"Configuration backup created: {backup_path}")
            
        except Exception as e:
            logger.warning(f"Failed to create configuration backup: {e}")
    
    def _cleanup_old_backups(self, backup_dir: Path) -> None:
        """Clean up old backup files."""
        try:
            max_backups = self.config.get("maxBackupFiles", 5)
            backup_files = sorted(
                backup_dir.glob("config_backup_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Remove old backups
            for old_backup in backup_files[max_backups:]:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup}")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")
    
    def _validate_config_value(self, key: str, value: Any) -> bool:
        """Validate a configuration value."""
        if key not in self._validation_rules:
            return True  # Allow unknown keys
        
        rule = self._validation_rules[key]
        
        # Type check
        if rule.type_check and not isinstance(value, rule.type_check):
            logger.warning(f"Config validation failed for {key}: wrong type")
            return False
        
        # Allowed values check
        if rule.allowed_values and value not in rule.allowed_values:
            logger.warning(f"Config validation failed for {key}: not in allowed values")
            return False
        
        # Range checks
        if rule.min_value is not None and value < rule.min_value:
            logger.warning(f"Config validation failed for {key}: below minimum")
            return False
        
        if rule.max_value is not None and value > rule.max_value:
            logger.warning(f"Config validation failed for {key}: above maximum")
            return False
        
        # Custom validator
        if rule.validator_func and not rule.validator_func(value):
            logger.warning(f"Config validation failed for {key}: custom validator")
            return False
        
        return True
    
    def _notify_change(self, key: str, old_value: Any, new_value: Any) -> None:
        """Notify callbacks of configuration change."""
        for callback in self._change_callbacks:
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                logger.error(f"Error in config change callback: {e}")
    
    # Public API methods
    
    async def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config.copy()
    
    async def get_value(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value."""
        return self.config.get(key, default)
    
    async def set_value(self, key: str, value: Any) -> bool:
        """Set a configuration value with validation."""
        # Validate the value
        if not self._validate_config_value(key, value):
            return False
        
        old_value = self.config.get(key)
        
        # Update configuration
        self.config[key] = value
        
        # Save if auto-save enabled
        if self.auto_save:
            await self._save_config()
        
        # Add to history
        self._add_to_history(key, old_value, value)
        
        # Notify callbacks
        self._notify_change(key, old_value, value)
        
        logger.info(f"Configuration updated: {key} = {value}")
        return True
    
    async def update_config(self, updates: Dict[str, Any]) -> Dict[str, bool]:
        """Update multiple configuration values."""
        results = {}
        
        for key, value in updates.items():
            results[key] = await self.set_value(key, value)
        
        return results
    
    async def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        old_config = self.config.copy()
        self.config = self._get_default_config()
        
        if self.auto_save:
            await self._save_config()
        
        logger.info("Configuration reset to defaults")
        
        # Notify of major change
        for callback in self._change_callbacks:
            try:
                callback("__reset__", old_config, self.config)
            except Exception as e:
                logger.error(f"Error in config reset callback: {e}")
    
    async def reload_from_file(self) -> bool:
        """Reload configuration from file."""
        try:
            old_config = self.config.copy()
            self._load_config()
            
            logger.info("Configuration reloaded from file")
            
            # Notify of reload
            for callback in self._change_callbacks:
                try:
                    callback("__reload__", old_config, self.config)
                except Exception as e:
                    logger.error(f"Error in config reload callback: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def _add_to_history(self, key: str, old_value: Any, new_value: Any) -> None:
        """Add change to history."""
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "key": key,
            "old_value": old_value,
            "new_value": new_value
        }
        
        self.config_history.append(change_record)
        
        # Limit history size
        if len(self.config_history) > self.max_history:
            self.config_history = self.config_history[-self.max_history:]
    
    def get_change_history(self) -> List[Dict[str, Any]]:
        """Get configuration change history."""
        return self.config_history.copy()
    
    def add_change_callback(self, callback: callable) -> None:
        """Add configuration change callback."""
        self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: callable) -> None:
        """Remove configuration change callback."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    # Security and validation methods
    
    async def validate_path(self, path: str) -> bool:
        """Validate if path is allowed based on configuration."""
        allowed_dirs = await self.get_value("allowedDirectories", [])
        
        # Empty list means full access (like Desktop Commander)
        if not allowed_dirs:
            return True
        
        try:
            resolved_path = str(Path(path).resolve()).lower()
            
            for allowed_dir in allowed_dirs:
                allowed_resolved = str(Path(allowed_dir).resolve()).lower()
                
                # Check if path is within allowed directory
                if resolved_path == allowed_resolved or resolved_path.startswith(allowed_resolved + os.sep):
                    return True
            
            return False
            
        except Exception:
            return False
    
    async def is_command_blocked(self, command: str) -> bool:
        """Check if command is in blocked list."""
        blocked_commands = await self.get_value("blockedCommands", [])
        
        command_lower = command.lower().strip()
        
        for blocked in blocked_commands:
            if blocked.lower() in command_lower:
                return True
        
        return False
    
    # Export and import methods
    
    async def export_config(self, export_path: str) -> bool:
        """Export configuration to file."""
        try:
            export_data = {
                "config": self.config,
                "history": self.config_history,
                "exported_at": datetime.now().isoformat(),
                "version": self.config.get("version", "1.0.0")
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration exported to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            return False
    
    async def import_config(self, import_path: str, merge: bool = True) -> bool:
        """Import configuration from file."""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            imported_config = import_data.get("config", {})
            
            if merge:
                # Merge with current config
                old_config = self.config.copy()
                self.config.update(imported_config)
            else:
                # Replace current config
                old_config = self.config.copy()
                self.config = imported_config
            
            # Validate all values
            invalid_keys = []
            for key, value in self.config.items():
                if not self._validate_config_value(key, value):
                    invalid_keys.append(key)
            
            if invalid_keys:
                logger.warning(f"Invalid configuration keys found during import: {invalid_keys}")
                # Restore old config for invalid keys
                for key in invalid_keys:
                    if key in old_config:
                        self.config[key] = old_config[key]
            
            if self.auto_save:
                await self._save_config()
            
            logger.info(f"Configuration imported from {import_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            return False


# Global configuration manager instance
_global_config_manager: Optional[ConfigManager] = None

async def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance."""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = await ConfigManager.get_instance()
    return _global_config_manager

# Convenience functions for quick access
async def get_config() -> Dict[str, Any]:
    """Get current configuration."""
    config_manager = await get_config_manager()
    return await config_manager.get_config()

async def get_config_value(key: str, default: Any = None) -> Any:
    """Get a specific configuration value."""
    config_manager = await get_config_manager()
    return await config_manager.get_value(key, default)

async def set_config_value(key: str, value: Any) -> bool:
    """Set a configuration value."""
    config_manager = await get_config_manager()
    return await config_manager.set_value(key, value)

async def validate_path_config(path: str) -> bool:
    """Validate if path is allowed."""
    config_manager = await get_config_manager()
    return await config_manager.validate_path(path)

async def is_command_blocked_config(command: str) -> bool:
    """Check if command is blocked."""
    config_manager = await get_config_manager()
    return await config_manager.is_command_blocked(command)