"""
Content validation utilities for extraction methods.
"""

import re
from typing import Optional
from urllib.parse import urlparse

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.research.extraction.validation")


class ContentValidator:
    """Sophisticated content validation with quality scoring."""
    
    def __init__(self, 
                 min_content_length: int = 150,
                 min_word_count: int = 20,
                 min_quality_score: float = 0.3):
        """
        Initialize content validator.
        
        Args:
            min_content_length: Minimum character count
            min_word_count: Minimum word count
            min_quality_score: Minimum quality score (0.0-1.0)
        """
        self.min_content_length = min_content_length
        self.min_word_count = min_word_count
        self.min_quality_score = min_quality_score
    
    def is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ('http', 'https') and parsed.netloc
        except:
            return False
    
    def is_valid_content(self, content: Optional[str]) -> bool:
        """
        Comprehensive content validation.
        
        Args:
            content: Content to validate
            
        Returns:
            True if content meets quality standards
        """
        if not content:
            return False
        
        content = content.strip()
        
        # Basic length checks
        if len(content) < self.min_content_length:
            logger.debug(f"Content too short: {len(content)} < {self.min_content_length}")
            return False
        
        words = content.split()
        if len(words) < self.min_word_count:
            logger.debug(f"Too few words: {len(words)} < {self.min_word_count}")
            return False
        
        # Quality scoring
        quality_score = self._calculate_quality_score(content)
        if quality_score < self.min_quality_score:
            logger.debug(f"Low quality score: {quality_score:.2f} < {self.min_quality_score}")
            return False
        
        return True
    
    def _calculate_quality_score(self, content: str) -> float:
        """
        Calculate content quality score (0.0-1.0).
        
        Higher score = better quality content
        """
        content_lower = content.lower()
        words = content.split()
        
        # Quality indicators (positive signals)
        quality_patterns = [
            r'\b(article|story|news|blog|post|content)\b',
            r'\b(paragraph|section|chapter|information)\b',
            r'\b(details|description|explanation|analysis)\b',
            r'[.!?]\s+[A-Z]',  # Sentence structure
            r'\b\w{4,}\b',     # Reasonable word length
        ]
        
        # Noise indicators (negative signals)
        noise_patterns = [
            r'\b(cookie|consent|gdpr|privacy policy)\b',
            r'\b(subscribe|newsletter|sign up|login)\b',
            r'\b(advertisement|sponsored|ad blocker)\b',
            r'\b(javascript|browser|enable|disabled)\b',
            r'\b(loading|please wait|error|404|403)\b',
            r'\b(captcha|verify|robot|automation)\b',
        ]
        
        # Count pattern matches
        quality_matches = sum(1 for pattern in quality_patterns 
                            if re.search(pattern, content_lower, re.IGNORECASE))
        noise_matches = sum(1 for pattern in noise_patterns 
                          if re.search(pattern, content_lower, re.IGNORECASE))
        
        # Sentence structure analysis
        sentences = re.split(r'[.!?]+', content)
        meaningful_sentences = [s for s in sentences if len(s.strip()) > 15]
        sentence_score = min(len(meaningful_sentences) / 10, 1.0)
        
        # Word diversity analysis
        unique_words = len(set(word.lower() for word in words if len(word) > 3))
        diversity_score = min(unique_words / len(words), 1.0) if words else 0
        
        # Calculate weighted quality score
        quality_component = min(quality_matches / 3, 1.0)  # Max 3 quality patterns
        noise_penalty = min(noise_matches / 5, 0.5)        # Max 50% penalty
        
        final_score = (
            0.4 * quality_component +
            0.3 * sentence_score +
            0.2 * diversity_score +
            0.1 * (1.0 if len(content) > 500 else len(content) / 500)
        ) - noise_penalty
        
        return max(0.0, min(1.0, final_score))
    
    def clean_content(self, content: str) -> str:
        """
        Clean and normalize content.
        
        Args:
            content: Raw content
            
        Returns:
            Cleaned content
        """
        if not content:
            return ""
        
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        # Remove common noise patterns
        noise_removals = [
            r'cookie\s+consent.*?\n',
            r'please\s+enable\s+javascript.*?\n',
            r'this\s+site\s+requires\s+javascript.*?\n',
        ]
        
        for pattern in noise_removals:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # Trim and return
        return content.strip()


# Global validator instance
_default_validator = ContentValidator()


def is_valid_url(url: str) -> bool:
    """Check if URL is valid."""
    return _default_validator.is_valid_url(url)


def is_valid_content(content: Optional[str]) -> bool:
    """Check if content is valid using default validator."""
    return _default_validator.is_valid_content(content)


def clean_content(content: str) -> str:
    """Clean content using default validator."""
    return _default_validator.clean_content(content)


def calculate_quality_score(content: str) -> float:
    """Calculate content quality score."""
    return _default_validator._calculate_quality_score(content)
