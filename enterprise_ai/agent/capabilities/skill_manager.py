"""
Skill management for individual Enterprise AI agents.
"""

from typing import Any, Dict, List
from enum import Enum

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.capabilities.skill_manager")


class SkillLevel(str, Enum):
    """Skill proficiency levels."""
    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillManager:
    """Skill manager for individual agents."""
    
    def __init__(self, agent_name: str):
        """Initialize skill manager."""
        self.agent_name = agent_name
        self.skills: Dict[str, SkillLevel] = {}
        self.skill_experience: Dict[str, int] = {}
        self.learning_goals: List[str] = []
        
        logger.info(f"SkillManager initialized for {agent_name}")
    
    def add_skill(self, skill_name: str, level: SkillLevel = SkillLevel.NOVICE) -> None:
        """Add a new skill."""
        self.skills[skill_name] = level
        self.skill_experience[skill_name] = 0
        logger.info(f"Added skill: {skill_name} at {level} level")
    
    def improve_skill(self, skill_name: str, experience_points: int = 1) -> bool:
        """Improve a skill with experience points."""
        if skill_name not in self.skills:
            self.add_skill(skill_name)
        
        self.skill_experience[skill_name] += experience_points
        return self._check_level_up(skill_name)
    
    def _check_level_up(self, skill_name: str) -> bool:
        """Check if skill should level up based on experience."""
        experience = self.skill_experience[skill_name]
        current_level = self.skills[skill_name]
        
        # Simple level up thresholds
        if current_level == SkillLevel.NOVICE and experience >= 10:
            self.skills[skill_name] = SkillLevel.INTERMEDIATE
            return True
        elif current_level == SkillLevel.INTERMEDIATE and experience >= 25:
            self.skills[skill_name] = SkillLevel.ADVANCED
            return True
        elif current_level == SkillLevel.ADVANCED and experience >= 50:
            self.skills[skill_name] = SkillLevel.EXPERT
            return True
        
        return False
    
    def get_skill_summary(self) -> Dict[str, Any]:
        """Get skill summary."""
        return {
            "agent": self.agent_name,
            "skills": dict(self.skills),
            "experience": dict(self.skill_experience),
            "learning_goals": list(self.learning_goals)
        }
