"""
Team lifecycle management for Enterprise AI.

This module provides functionality for managing team lifecycle
events, including initialization, state persistence, and termination.
"""

import asyncio
import json
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, cast

from enterprise_ai.agent.architecture.utils import generate_id
from enterprise_ai.logger import get_logger
from enterprise_ai.team.core.types import TeamProtocol

logger = get_logger("team.architecture.lifecycle")


class TeamState(Enum):
    """Enumeration of team states."""
    
    UNINITIALIZED = "uninitialized"  # Team has been created but not initialized
    INITIALIZING = "initializing"     # Team is currently initializing
    ACTIVE = "active"                 # Team is active and ready for use
    PAUSED = "paused"                 # Team is temporarily inactive but can be resumed
    TERMINATING = "terminating"       # Team is in the process of terminating
    TERMINATED = "terminated"         # Team has been terminated
    FAILED = "failed"                 # Team failed during initialization or operation


class LifecycleManager:
    """Team lifecycle manager.
    
    This component handles all aspects of team lifecycle management, including:
    - Initialization of team components
    - Termination and cleanup
    - State persistence and recovery
    - Configuration management
    - Health monitoring
    """
    
    def __init__(self, team: "TeamProtocol"):
        """Initialize the lifecycle manager.
        
        Args:
            team: Team that this manager belongs to
        """
        self._team = team
        self._state = TeamState.UNINITIALIZED
        self._config: Dict[str, Any] = {}
        self._state_dir: Optional[str] = None
        self._last_save: Optional[datetime] = None
        self._initialization_time: Optional[datetime] = None
        self._termination_time: Optional[datetime] = None
        self._error_history: List[Dict[str, Any]] = []
        
        logger.info(f"Initialized lifecycle manager for team {team.id}")
    
    @property
    def state(self) -> TeamState:
        """Get the current team state.
        
        Returns:
            Current team state
        """
        return self._state
    
    def set_state(self, state: TeamState) -> None:
        """Set the team state.
        
        Args:
            state: New team state
        """
        old_state = self._state
        self._state = state
        
        logger.info(f"Team {self._team.id} state changed from {old_state.value} to {state.value}")
        
        # Record timestamps for state transitions
        if state == TeamState.ACTIVE and not self._initialization_time:
            self._initialization_time = datetime.now()
        elif state == TeamState.TERMINATED and not self._termination_time:
            self._termination_time = datetime.now()
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize the team.
        
        Args:
            config: Optional configuration parameters
            
        Returns:
            True if initialization succeeded, False otherwise
        """
        # Update state
        if self._state != TeamState.UNINITIALIZED:
            logger.warning(
                f"Cannot initialize team {self._team.id} in state {self._state.value}"
            )
            return False
        
        self.set_state(TeamState.INITIALIZING)
        
        # Update configuration
        if config:
            self._config.update(config)
        
        # Set up state directory if specified
        if "state_dir" in self._config:
            self._state_dir = self._config["state_dir"]
            os.makedirs(self._state_dir, exist_ok=True)
        
        try:
            # Perform team-specific initialization
            result = await self._team.initialize(**self._config)
            
            if result:
                # Update state to active
                self.set_state(TeamState.ACTIVE)
                logger.info(f"Successfully initialized team {self._team.id}")
            else:
                # Update state to failed
                self.set_state(TeamState.FAILED)
                logger.error(f"Failed to initialize team {self._team.id}")
            
            return result
        except Exception as e:
            # Record error
            self._record_error("initialization_error", str(e))
            
            # Update state to failed
            self.set_state(TeamState.FAILED)
            logger.error(f"Error initializing team {self._team.id}: {e}")
            
            return False
    
    async def terminate(self) -> bool:
        """Terminate the team.
        
        Returns:
            True if termination succeeded, False otherwise
        """
        # Update state
        if self._state == TeamState.TERMINATED:
            logger.warning(f"Team {self._team.id} is already terminated")
            return True
        
        if self._state == TeamState.TERMINATING:
            logger.warning(f"Team {self._team.id} is already terminating")
            return False
        
        self.set_state(TeamState.TERMINATING)
        
        try:
            # Perform team-specific termination
            result = await self._team.terminate()
            
            if result:
                # Update state to terminated
                self.set_state(TeamState.TERMINATED)
                logger.info(f"Successfully terminated team {self._team.id}")
            else:
                # Update state to failed
                self.set_state(TeamState.FAILED)
                logger.error(f"Failed to terminate team {self._team.id}")
            
            return result
        except Exception as e:
            # Record error
            self._record_error("termination_error", str(e))
            
            # Update state to failed
            self.set_state(TeamState.FAILED)
            logger.error(f"Error terminating team {self._team.id}: {e}")
            
            return False
    
    def pause(self) -> bool:
        """Pause the team.
        
        Returns:
            True if pause succeeded, False otherwise
        """
        # Can only pause active teams
        if self._state != TeamState.ACTIVE:
            logger.warning(
                f"Cannot pause team {self._team.id} in state {self._state.value}"
            )
            return False
        
        # Update state
        self.set_state(TeamState.PAUSED)
        logger.info(f"Paused team {self._team.id}")
        
        return True
    
    def resume(self) -> bool:
        """Resume the team.
        
        Returns:
            True if resume succeeded, False otherwise
        """
        # Can only resume paused teams
        if self._state != TeamState.PAUSED:
            logger.warning(
                f"Cannot resume team {self._team.id} in state {self._state.value}"
            )
            return False
        
        # Update state
        self.set_state(TeamState.ACTIVE)
        logger.info(f"Resumed team {self._team.id}")
        
        return True
    
    def save_state(self) -> bool:
        """Save team state to disk.
        
        Returns:
            True if state was saved successfully, False otherwise
        """
        if not self._state_dir:
            logger.warning(f"No state directory configured for team {self._team.id}")
            return False
        
        try:
            # Create state file path
            state_file = os.path.join(self._state_dir, f"{self._team.id}.json")
            
            # Get team status
            team_status = self._team.get_status()
            
            # Add lifecycle information
            state_data = {
                "team_id": self._team.id,
                "state": self._state.value,
                "config": self._config,
                "timestamp": datetime.now().isoformat(),
                "initialization_time": self._initialization_time.isoformat() if self._initialization_time else None,
                "termination_time": self._termination_time.isoformat() if self._termination_time else None,
                "status": team_status,
            }
            
            # Write to file
            with open(state_file, "w") as f:
                json.dump(state_data, f, indent=2)
            
            # Update last save time
            self._last_save = datetime.now()
            
            logger.info(f"Saved state for team {self._team.id} to {state_file}")
            return True
        except Exception as e:
            # Record error
            self._record_error("state_save_error", str(e))
            
            logger.error(f"Error saving team state for {self._team.id}: {e}")
            return False
    
    def load_state(self) -> bool:
        """Load team state from disk.
        
        Returns:
            True if state was loaded successfully, False otherwise
        """
        if not self._state_dir:
            logger.warning(f"No state directory configured for team {self._team.id}")
            return False
        
        try:
            # Create state file path
            state_file = os.path.join(self._state_dir, f"{self._team.id}.json")
            
            # Check if file exists
            if not os.path.exists(state_file):
                logger.warning(f"No state file found for team {self._team.id}")
                return False
            
            # Read from file
            with open(state_file, "r") as f:
                state_data = json.load(f)
            
            # Update configuration
            if "config" in state_data:
                self._config.update(state_data["config"])
            
            # Set state if valid
            if "state" in state_data:
                try:
                    self.set_state(TeamState(state_data["state"]))
                except ValueError:
                    logger.warning(f"Invalid state value in state file: {state_data['state']}")
            
            # Parse timestamps
            if "initialization_time" in state_data and state_data["initialization_time"]:
                try:
                    self._initialization_time = datetime.fromisoformat(state_data["initialization_time"])
                except ValueError:
                    logger.warning(f"Invalid initialization time in state file: {state_data['initialization_time']}")
            
            if "termination_time" in state_data and state_data["termination_time"]:
                try:
                    self._termination_time = datetime.fromisoformat(state_data["termination_time"])
                except ValueError:
                    logger.warning(f"Invalid termination time in state file: {state_data['termination_time']}")
            
            logger.info(f"Loaded state for team {self._team.id} from {state_file}")
            return True
        except Exception as e:
            # Record error
            self._record_error("state_load_error", str(e))
            
            logger.error(f"Error loading team state for {self._team.id}: {e}")
            return False
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update team configuration.
        
        Args:
            config: New configuration to merge with existing config
        """
        self._config.update(config)
        logger.info(f"Updated configuration for team {self._team.id}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get team configuration.
        
        Returns:
            Current configuration
        """
        return self._config.copy()
    
    def get_uptime(self) -> Optional[float]:
        """Get team uptime in seconds.
        
        Returns:
            Uptime in seconds or None if not initialized
        """
        if not self._initialization_time:
            return None
        
        # If terminated, calculate time between initialization and termination
        if self._state == TeamState.TERMINATED and self._termination_time:
            return (self._termination_time - self._initialization_time).total_seconds()
        
        # Otherwise, calculate time since initialization
        return (datetime.now() - self._initialization_time).total_seconds()
    
    def get_status(self) -> Dict[str, Any]:
        """Get lifecycle status information.
        
        Returns:
            Dictionary of lifecycle status information
        """
        return {
            "state": self._state.value,
            "initialization_time": self._initialization_time.isoformat() if self._initialization_time else None,
            "termination_time": self._termination_time.isoformat() if self._termination_time else None,
            "uptime": self.get_uptime(),
            "last_save": self._last_save.isoformat() if self._last_save else None,
            "error_count": len(self._error_history),
        }
    
    def _record_error(self, error_type: str, error_message: str) -> None:
        """Record an error in the history.
        
        Args:
            error_type: Type of error
            error_message: Error message
        """
        self._error_history.append({
            "type": error_type,
            "message": error_message,
            "timestamp": datetime.now().isoformat(),
        })
