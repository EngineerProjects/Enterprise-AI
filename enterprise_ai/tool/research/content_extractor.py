"""
Content extraction for Enterprise AI Research - OPTIMIZED.

This module provides a clean import bridge to the optimized modular extraction system.
All functionality is now powered by the enterprise-grade extraction engine.

Backward Compatibility:
- AdvancedContentExtractor: Legacy interface (same API as before)
- create_content_extractor: Legacy factory function

New Optimized API:
- EnterpriseContentExtractor: Full-featured new interface
- create_enterprise_extractor: Optimized factory function

Usage (Legacy - works unchanged):
    from enterprise_ai.tool.research.content_extractor import AdvancedContentExtractor
    extractor = AdvancedContentExtractor(timeout=25)
    content = await extractor.extract("https://example.com")

Usage (New - recommended):
    from enterprise_ai.tool.research.content_extractor import EnterpriseContentExtractor
    extractor = EnterpriseContentExtractor(timeout=25, enable_js_extraction=True)
    result = await extractor.extract("https://example.com")
"""

from typing import Optional, Dict, Any

# Import the optimized extraction system
from enterprise_ai.tool.research.extraction import (
    EnterpriseContentExtractor,
    AdvancedContentExtractor as ModularAdvancedExtractor,
    create_enterprise_extractor,
    ExtractionResult
)
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.research.content_extractor")


class AdvancedContentExtractor:
    """
    Legacy backward compatibility wrapper.
    
    This class maintains the exact same interface as the original
    AdvancedContentExtractor while using the optimized modular system.
    
    For new code, consider using EnterpriseContentExtractor directly
    for access to full features and better performance.
    """
    
    def __init__(self, timeout: int = 25):
        """
        Initialize with legacy interface.
        
        Args:
            timeout: Timeout in seconds for extraction attempts
        """
        self.timeout = timeout
        
        # Use the optimized modular system
        self._extractor = ModularAdvancedExtractor(timeout=timeout)
        
        logger.debug(f"AdvancedContentExtractor initialized with timeout={timeout}s")
    
    async def extract(self, url: str) -> Optional[str]:
        """
        Extract content from URL (legacy interface).
        
        Args:
            url: URL to extract content from
            
        Returns:
            Extracted content as string, or None if extraction fails
        """
        return await self._extractor.extract(url)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics in legacy format."""
        return self._extractor.get_stats()


# Factory function for backward compatibility
def create_content_extractor(timeout: int = 25) -> AdvancedContentExtractor:
    """
    Create a content extractor instance (legacy factory).
    
    Args:
        timeout: Timeout in seconds
        
    Returns:
        AdvancedContentExtractor instance
    """
    return AdvancedContentExtractor(timeout=timeout)


# Export both legacy and new interfaces
__all__ = [
    # Legacy backward compatibility (same API as before)
    "AdvancedContentExtractor",
    "create_content_extractor",
    
    # New optimized system (recommended for new code)
    "EnterpriseContentExtractor", 
    "create_enterprise_extractor",
    "ExtractionResult",
]

# Log successful initialization
logger.info("Content extraction module loaded with optimized modular system")
