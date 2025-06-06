"""
Personal memory management for individual Enterprise AI agents.
Handles memory storage, retrieval, and organization for single agents.
"""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.memory.personal")


@dataclass
class MemoryEntry:
    """Individual memory entry for an agent."""
    content: str
    entry_type: str = "general"  # general, task, learning, reflection
    timestamp: float = field(default_factory=time.time)
    importance: int = 1  # 1-10 scale
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PersonalMemoryManager:
    """Personal memory manager for individual agents."""
    
    def __init__(
        self,
        agent_name: str,
        max_short_term: int = 50,
        max_long_term: int = 500,
        importance_threshold: int = 5
    ):
        """Initialize personal memory manager."""
        self.agent_name = agent_name
        self.max_short_term = max_short_term
        self.max_long_term = max_long_term
        self.importance_threshold = importance_threshold
        
        # Memory storage
        self.short_term_memory: List[MemoryEntry] = []
        self.long_term_memory: List[MemoryEntry] = []
        self.reflection_memory: List[MemoryEntry] = []
        
        logger.info(f"PersonalMemoryManager initialized for {agent_name}")

    def add_memory(
        self,
        content: str,
        entry_type: str = "general",
        importance: int = 1,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Add a new memory entry."""
        entry = MemoryEntry(
            content=content,
            entry_type=entry_type,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        # Add to short-term memory
        self.short_term_memory.append(entry)
        
        # If important enough, also add to long-term
        if importance >= self.importance_threshold:
            self.long_term_memory.append(entry)
        
        # Manage memory size limits
        self._manage_memory_limits()
        
        logger.debug(f"Added memory entry: {content[:50]}...")
    
    def get_recent_memories(self, count: int = 10, entry_type: str = None) -> List[MemoryEntry]:
        """Get recent memories from short-term storage."""
        memories = self.short_term_memory
        
        if entry_type:
            memories = [m for m in memories if m.entry_type == entry_type]
        
        # Return most recent first
        return sorted(memories, key=lambda x: x.timestamp, reverse=True)[:count]
    
    def search_memories(
        self,
        query: str,
        search_type: str = "content",  # content, tags, type
        include_long_term: bool = True
    ) -> List[MemoryEntry]:
        """Search memories by content, tags, or type."""
        all_memories = self.short_term_memory.copy()
        if include_long_term:
            all_memories.extend(self.long_term_memory)
        
        results = []
        query_lower = query.lower()
        
        for memory in all_memories:
            if search_type == "content" and query_lower in memory.content.lower():
                results.append(memory)
            elif search_type == "tags" and any(query_lower in tag.lower() for tag in memory.tags):
                results.append(memory)
            elif search_type == "type" and query_lower in memory.entry_type.lower():
                results.append(memory)
        
        # Sort by relevance (timestamp for now, could be improved)
        return sorted(results, key=lambda x: x.timestamp, reverse=True)

    def _manage_memory_limits(self) -> None:
        """Manage memory storage limits."""
        # Trim short-term memory if over limit
        if len(self.short_term_memory) > self.max_short_term:
            # Keep most recent and most important
            sorted_memories = sorted(
                self.short_term_memory,
                key=lambda x: (x.importance, x.timestamp),
                reverse=True
            )
            self.short_term_memory = sorted_memories[:self.max_short_term]
        
        # Trim long-term memory if over limit
        if len(self.long_term_memory) > self.max_long_term:
            # Keep most important
            sorted_memories = sorted(
                self.long_term_memory,
                key=lambda x: x.importance,
                reverse=True
            )
            self.long_term_memory = sorted_memories[:self.max_long_term]
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get summary of current memory state."""
        return {
            "agent": self.agent_name,
            "short_term_count": len(self.short_term_memory),
            "long_term_count": len(self.long_term_memory),
            "reflection_count": len(self.reflection_memory),
            "recent_entries": [
                {
                    "content": entry.content[:50] + "...",
                    "type": entry.entry_type,
                    "importance": entry.importance,
                    "timestamp": entry.timestamp
                }
                for entry in self.get_recent_memories(5)
            ]
        }
    
    def clear_memory(self, memory_type: str = "all") -> None:
        """Clear specific type of memory."""
        if memory_type == "all":
            self.short_term_memory.clear()
            self.long_term_memory.clear()
            self.reflection_memory.clear()
        elif memory_type == "short_term":
            self.short_term_memory.clear()
        elif memory_type == "long_term":
            self.long_term_memory.clear()
        elif memory_type == "reflection":
            self.reflection_memory.clear()
        
        logger.info(f"Cleared {memory_type} memory for {self.agent_name}")
