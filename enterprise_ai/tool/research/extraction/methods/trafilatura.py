"""
Trafilatura extraction method - fastest and most reliable.
"""

import asyncio
from typing import List

from .base import BaseExtractionMethod, ExtractionResult
from ..validation import is_valid_content


class TrafilaturaMethod(BaseExtractionMethod):
    """Trafilatura extraction method - optimized for speed and reliability."""
    
    @property
    def dependencies(self) -> List[str]:
        """Required dependencies."""
        return ["trafilatura"]
    
    async def extract(self, url: str) -> ExtractionResult:
        """Extract content using Trafilatura."""
        if not self.is_available():
            return self.create_result(url, error="Trafilatura not installed")
        
        try:
            import trafilatura
            from trafilatura.settings import use_config
            
            # Configure trafilatura for optimal extraction
            config = use_config()
            config.set("DEFAULT", "EXTRACTION_TIMEOUT", str(self.timeout))
            config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "150")
            
            # Fetch content
            content = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: trafilatura.fetch_url(url, config=config)
                ),
                timeout=self.timeout
            )
            
            if not content:
                return self.create_result(url, error="Failed to fetch content")
            
            # Extract text with optimized settings
            text = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: trafilatura.extract(
                    content,
                    include_comments=False,
                    include_tables=True,
                    include_formatting=False,
                    include_links=False,
                    deduplicate=True,
                    config=config
                )
            )
            
            if text and is_valid_content(text):
                return self.create_result(url, content=text.strip())
            
            return self.create_result(url, error="Content validation failed")
            
        except asyncio.TimeoutError:
            return self.create_result(url, error=f"Timeout after {self.timeout}s")
        except Exception as e:
            return self.create_result(url, error=f"Trafilatura error: {str(e)}")
