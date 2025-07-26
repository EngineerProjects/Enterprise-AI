"""
Requests + Readability extraction method - reliable for main content.
"""

import asyncio
from typing import List

from .base import HTTPMethod, ExtractionResult
from ..validation import is_valid_content


class ReadabilityMethod(HTTPMethod):
    """Requests + Readability method for main content extraction."""
    
    @property
    def dependencies(self) -> List[str]:
        """Required dependencies."""
        return ["aiohttp", "readability", "bs4"]  # bs4 is the import name for beautifulsoup4
    
    async def extract(self, url: str) -> ExtractionResult:
        """Extract content using Requests + Readability."""
        if not self.is_available():
            return self.create_result(url, error="Required packages not installed")
        
        try:
            import aiohttp
            from readability import Document
            from bs4 import BeautifulSoup
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers = self.get_headers()
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url, ssl=False) as response:
                    if response.status >= 400:
                        return self.create_result(
                            url, 
                            error=f"HTTP {response.status}",
                            status_code=response.status
                        )
                    
                    html = await response.text()
            
            # Use readability to extract main content
            doc = Document(html)
            content_html = doc.summary()
            title = doc.title()
            
            # Convert HTML to clean text
            soup = BeautifulSoup(content_html, 'html.parser')
            
            # Remove remaining noise elements
            for element in soup(['script', 'style', 'nav', 'aside']):
                element.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            
            # Add title if available and meaningful
            if title and len(title.strip()) > 5 and title.strip().lower() not in text.lower()[:200]:
                text = f"{title.strip()}\n\n{text}"
            
            if is_valid_content(text):
                return self.create_result(
                    url, 
                    content=text,
                    status_code=response.status
                )
            
            return self.create_result(url, error="Content validation failed")
            
        except asyncio.TimeoutError:
            return self.create_result(url, error=f"Timeout after {self.timeout}s")
        except Exception as e:
            return self.create_result(url, error=f"Readability error: {str(e)}")
