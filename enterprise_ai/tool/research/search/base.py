"""Base class definitions for search engines."""

from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class SearchItem(BaseModel):
    """Represents a single search result item."""

    title: str = Field(description="The title of the search result")
    url: str = Field(description="The URL of the search result")
    description: Optional[str] = Field(
        default=None, description="A description or snippet of the search result"
    )

    def __str__(self) -> str:
        """String representation of a search result item."""
        return f"{self.title} - {self.url}"


class WebSearchEngine(ABC):
    """Base class for web search engines with improved structure."""

    def __init__(self) -> None:
        """Initialize the search engine."""
        pass

    @abstractmethod
    def perform_search(
        self, 
        query: str, 
        num_results: int = 10, 
        lang: Optional[str] = None,
        country: Optional[str] = None,
        **kwargs: Any
    ) -> List[SearchItem]:
        """
        Perform a web search and return a list of search items.

        Args:
            query: The search query to submit to the search engine
            num_results: The number of search results to return (default: 10)
            lang: Language code for search results
            country: Country code for search results
            **kwargs: Additional keyword arguments specific to the engine

        Returns:
            A list of SearchItem objects matching the search query

        Raises:
            Exception: If the search fails or encounters an error
        """
        raise NotImplementedError("Subclasses must implement perform_search method")

    def is_available(self) -> bool:
        """
        Check if this search engine is available and functional.

        Returns:
            True if the search engine can be used, False otherwise
        """
        # Default implementation - subclasses can override
        return True

    def get_engine_name(self) -> str:
        """
        Get the name of this search engine.

        Returns:
            String name of the search engine
        """
        return self.__class__.__name__.replace("SearchEngine", "").lower()