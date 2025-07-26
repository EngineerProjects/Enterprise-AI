"""
Base classes and interfaces for content extraction methods.
"""

import asyncio
import random
import ssl
import certifi
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.research.extraction.base")


@dataclass
class ExtractionResult:
    """Result of a content extraction attempt."""
    content: Optional[str] = None
    success: bool = False
    method: str = ""
    url: str = ""
    status_code: Optional[int] = None
    error: Optional[str] = None
    char_count: int = 0
    word_count: int = 0
    extraction_time: float = 0.0
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.content:
            self.char_count = len(self.content)
            self.word_count = len(self.content.split())


class BaseExtractionMethod(ABC):
    """
    Base class for all content extraction methods.
    
    Each method implements a specific extraction technique
    (e.g., Trafilatura, Playwright, etc.)
    """
    
    def __init__(self, timeout: int = 25, **kwargs):
        """Initialize the extraction method."""
        self.timeout = timeout
        self.config = kwargs
        self.name = self.__class__.__name__.lower().replace('method', '')
        
    @abstractmethod
    async def extract(self, url: str) -> ExtractionResult:
        """
        Extract content from URL using this method.
        
        Args:
            url: URL to extract from
            
        Returns:
            ExtractionResult with content and metadata
        """
        pass
    
    @property
    @abstractmethod
    def dependencies(self) -> List[str]:
        """List of required Python packages for this method."""
        pass
    
    def is_available(self) -> bool:
        """Check if this method is available (dependencies installed)."""
        try:
            for dep in self.dependencies:
                __import__(dep)
            return True
        except ImportError:
            return False
    
    def create_result(self, url: str, content: Optional[str] = None, 
                     error: Optional[str] = None, **kwargs) -> ExtractionResult:
        """Helper to create ExtractionResult."""
        return ExtractionResult(
            content=content,
            success=content is not None and len(content.strip()) > 0,
            method=self.name,
            url=url,
            error=error,
            **kwargs
        )


class HTTPMethod(BaseExtractionMethod):
    """Base class for HTTP-based extraction methods."""
    
    # Common user agents for rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    
    def __init__(self, timeout: int = 25, **kwargs):
        super().__init__(timeout, **kwargs)
        
        # Create SSL context for HTTPS requests
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with random user agent."""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }


class BrowserMethod(BaseExtractionMethod):
    """Base class for browser-based extraction methods."""
    
    def get_browser_args(self) -> List[str]:
        """Get common browser arguments for headless operation."""
        return [
            '--headless',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-extensions',
            '--disable-plugins',
            '--disable-gpu',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
        ]
    
    def get_user_agent(self) -> str:
        """Get random user agent for browser."""
        return random.choice(HTTPMethod.USER_AGENTS)
