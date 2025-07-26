"""
Newspaper4k extraction method - excellent for news and articles.
"""

import asyncio
from typing import List

from .base import HTTPMethod, ExtractionResult
from ..validation import is_valid_content


class NewspaperMethod(HTTPMethod):
    """Newspaper4k method optimized for news and article content."""
    
    @property
    def dependencies(self) -> List[str]:
        """Required dependencies."""
        return ["newspaper"]
    
    async def extract(self, url: str) -> ExtractionResult:
        """Extract content using Newspaper4k."""
        if not self.is_available():
            return self.create_result(url, error="Newspaper4k not installed")
        
        try:
            from newspaper import Article
            
            article = Article(url)
            
            # Configure article with optimized settings
            article.set_config({
                'browser_user_agent': self.get_user_agent(),
                'request_timeout': self.timeout,
                'number_threads': 1,
                'thread_timeout_seconds': self.timeout,
                'ignored_content_types_defaults': {
                    'application/pdf', 'application/x-pdf',
                    'application/msword', 'application/vnd.ms-excel'
                }
            })
            
            # Download with timeout
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, article.download),
                timeout=self.timeout
            )
            
            # Parse content
            await asyncio.get_event_loop().run_in_executor(None, article.parse)
            
            # Get article text
            text = article.text
            title = article.title
            
            # Combine title and text if both available
            if title and text and title.strip() not in text[:200]:
                content = f"{title.strip()}\n\n{text.strip()}"
            else:
                content = text.strip() if text else ""
            
            if content and is_valid_content(content):
                return self.create_result(url, content=content)
            
            return self.create_result(url, error="No valid content extracted")
            
        except asyncio.TimeoutError:
            return self.create_result(url, error=f"Timeout after {self.timeout}s")
        except Exception as e:
            return self.create_result(url, error=f"Newspaper error: {str(e)}")
