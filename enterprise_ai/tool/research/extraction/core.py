"""
Core extraction engine for Enterprise AI content extraction.

This module provides the main ExtractorEngine that orchestrates
multiple extraction methods in an intelligent cascade system.
"""

import asyncio
import time
import random
from typing import List, Optional, Dict, Any

from .methods import (
    ExtractionResult, 
    EXTRACTION_METHODS, 
    FAST_METHODS, 
    SLOW_METHODS,
    get_available_methods,
    create_method
)
from .validation import is_valid_url
from .stats import StatsTracker

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.research.extraction.core")


class ExtractorEngine:
    """
    Core extraction engine with intelligent method cascade.
    
    Features:
    - Smart method ordering based on URL patterns
    - Configurable timeout and retry logic  
    - Performance-focused method selection
    - Comprehensive statistics tracking
    - Graceful handling of missing dependencies
    """
    
    def __init__(self,
                 timeout: int = 25,
                 min_content_length: int = 150,
                 retry_attempts: int = 1,
                 enable_slow_methods: bool = True,
                 preferred_methods: Optional[List[str]] = None):
        """
        Initialize the extraction engine.
        
        Args:
            timeout: Timeout per method in seconds
            min_content_length: Minimum content length for validation
            retry_attempts: Number of retry attempts per method
            enable_slow_methods: Whether to enable slow methods (playwright, selenium)
            preferred_methods: List of preferred methods to try first
        """
        self.timeout = timeout
        self.min_content_length = min_content_length
        self.retry_attempts = retry_attempts
        self.enable_slow_methods = enable_slow_methods
        self.preferred_methods = preferred_methods or []
        
        # Initialize statistics tracking
        self.stats = StatsTracker()
        
        # Cache available methods
        self._available_methods = None
        self._method_instances = {}
    
    def get_available_methods(self) -> List[str]:
        """Get list of available extraction methods."""
        if self._available_methods is None:
            self._available_methods = get_available_methods()
            logger.info(f"Available extraction methods: {self._available_methods}")
        
        return self._available_methods
    
    def _get_method_instance(self, method_name: str):
        """Get or create method instance with caching."""
        if method_name not in self._method_instances:
            try:
                self._method_instances[method_name] = create_method(
                    method_name, 
                    timeout=self.timeout,
                    min_content_length=self.min_content_length
                )
            except (ValueError, ImportError) as e:
                logger.debug(f"Cannot create method {method_name}: {e}")
                return None
        
        return self._method_instances.get(method_name)
    
    def _build_method_cascade(self, url: str) -> List[str]:
        """
        Build intelligent method cascade based on URL and configuration.
        
        Args:
            url: URL to extract from
            
        Returns:
            Ordered list of method names to try
        """
        available = self.get_available_methods()
        if not available:
            logger.warning("No extraction methods available!")
            return []
        
        # Start with preferred methods if specified
        cascade = []
        for method in self.preferred_methods:
            if method in available:
                cascade.append(method)
        
        # Add fast methods first
        fast_available = [m for m in FAST_METHODS if m in available and m not in cascade]
        cascade.extend(fast_available)
        
        # Add slow methods if enabled
        if self.enable_slow_methods:
            slow_available = [m for m in SLOW_METHODS if m in available and m not in cascade]
            cascade.extend(slow_available)
        
        # Add any remaining methods
        remaining = [m for m in available if m not in cascade]
        cascade.extend(remaining)
        
        logger.debug(f"Method cascade for {url}: {cascade}")
        return cascade
    
    async def extract(self, url: str, preferred_method: Optional[str] = None) -> ExtractionResult:
        """
        Extract content using intelligent method cascade.
        
        Args:
            url: URL to extract content from
            preferred_method: Specific method to try first
            
        Returns:
            ExtractionResult with content and metadata
        """
        start_time = time.time()
        
        if not is_valid_url(url):
            return ExtractionResult(
                url=url,
                error="Invalid URL format",
                extraction_time=time.time() - start_time
            )
        
        # Build method cascade
        if preferred_method and preferred_method in self.get_available_methods():
            methods = [preferred_method] + [m for m in self._build_method_cascade(url) 
                                          if m != preferred_method]
        else:
            methods = self._build_method_cascade(url)
        
        if not methods:
            return ExtractionResult(
                url=url,
                error="No extraction methods available",
                extraction_time=time.time() - start_time
            )
        
        # Try each method in cascade
        for method_name in methods:
            logger.debug(f"Trying {method_name} for: {url}")
            
            self.stats.track_attempt(method_name)
            
            method_start = time.time()
            result = await self._try_method_with_retry(method_name, url)
            method_time = time.time() - method_start
            
            if result.success:
                logger.debug(f"{method_name} succeeded for: {url} ({result.char_count} chars)")
                self.stats.track_success(method_name, method_time)
                result.extraction_time = time.time() - start_time
                return result
            else:
                logger.debug(f"{method_name} failed for: {url} - {result.error}")
        
        # All methods failed
        total_time = time.time() - start_time
        self.stats.track_failure(total_time)
        
        return ExtractionResult(
            url=url,
            error="All extraction methods failed",
            extraction_time=total_time
        )
    
    async def _try_method_with_retry(self, method_name: str, url: str) -> ExtractionResult:
        """Try a method with retry logic."""
        method = self._get_method_instance(method_name)
        if not method:
            return ExtractionResult(
                url=url,
                method=method_name,
                error=f"Method {method_name} not available"
            )
        
        last_error = None
        
        for attempt in range(self.retry_attempts + 1):
            try:
                if attempt > 0:
                    # Brief delay between retries
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    logger.debug(f"Retry {attempt} for {method_name}: {url}")
                
                result = await method.extract(url)
                if result.success:
                    return result
                last_error = result.error
                
            except Exception as e:
                last_error = str(e)
                logger.debug(f"{method_name} attempt {attempt} error: {e}")
        
        return ExtractionResult(
            url=url,
            method=method_name,
            error=last_error or f"{method_name} failed after {self.retry_attempts + 1} attempts"
        )
    
    async def bulk_extract(self, urls: List[str], 
                          max_concurrent: int = 5) -> List[ExtractionResult]:
        """
        Extract content from multiple URLs concurrently.
        
        Args:
            urls: List of URLs to extract from
            max_concurrent: Maximum concurrent extractions
            
        Returns:
            List of ExtractionResults
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(url: str) -> ExtractionResult:
            async with semaphore:
                return await self.extract(url)
        
        tasks = [extract_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive extraction statistics."""
        stats = self.stats.get_stats()
        
        # Add configuration info
        stats["configuration"] = {
            "timeout": self.timeout,
            "min_content_length": self.min_content_length,
            "retry_attempts": self.retry_attempts,
            "enable_slow_methods": self.enable_slow_methods,
            "available_methods": self.get_available_methods(),
            "preferred_methods": self.preferred_methods
        }
        
        return stats
    
    def get_legacy_stats(self) -> Dict[str, Any]:
        """Get statistics in legacy format for backward compatibility."""
        return self.stats.get_legacy_stats()
    
    def reset_stats(self):
        """Reset all statistics."""
        self.stats.reset()


# Factory function for easy creation
def create_extractor(timeout: int = 25,
                    min_content_length: int = 150,
                    enable_slow_methods: bool = True,
                    preferred_methods: Optional[List[str]] = None) -> ExtractorEngine:
    """
    Create an optimized extractor engine.
    
    Args:
        timeout: Timeout per method in seconds
        min_content_length: Minimum content length
        enable_slow_methods: Whether to enable slow methods (selenium, etc.)
        preferred_methods: List of preferred methods to try first
        
    Returns:
        Configured ExtractorEngine instance
    """
    return ExtractorEngine(
        timeout=timeout,
        min_content_length=min_content_length,
        retry_attempts=1,  # Reduced for better performance
        enable_slow_methods=enable_slow_methods,
        preferred_methods=preferred_methods
    )
