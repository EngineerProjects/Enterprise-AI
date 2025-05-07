"""Web search tool for Enterprise AI."""

import asyncio
import base64
import time
from typing import Any, Dict, List, Optional, Set, Union, cast
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from enterprise_ai.config import get_config
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.research.search import (
    BaiduSearchEngine,
    BingSearchEngine,
    DuckDuckGoSearchEngine,
    GoogleSearchEngine,
    SearchItem,
    WebSearchEngine,
)
from enterprise_ai.tool.core.registry import register_tool

logger = get_logger("tool.research.web_search")

# Rate limiting settings - default values that can be overridden via config
DEFAULT_RATE_LIMIT = 2  # requests per second
DEFAULT_RATE_LIMIT_PERIOD = 60  # seconds between resets
DEFAULT_MAX_REQUESTS = 100  # maximum requests in period


class SearchResult(BaseModel):
    """Represents a single search result returned by a search engine."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    position: int = Field(description="Position in search results")
    url: str = Field(description="URL of the search result")
    title: str = Field(default="", description="Title of the search result")
    description: str = Field(default="", description="Description or snippet of the search result")
    source: str = Field(description="The search engine that provided this result")
    raw_content: Optional[str] = Field(
        default=None, description="Raw content from the search result page if available"
    )

    def __str__(self) -> str:
        """String representation of a search result."""
        return f"{self.title} ({self.url})"

class SearchMetadata(BaseModel):
    """Metadata about the search operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_results: int = Field(description="Total number of results found")
    language: str = Field(description="Language code used for the search")
    country: str = Field(description="Country code used for the search")
    time_taken: float = Field(default=0.0, description="Time taken for the search in seconds")
    engines_tried: List[str] = Field(
        default_factory=list, description="Search engines that were tried"
    )
    tool_name: Optional[str] = Field(
        default=None, description="Name of the tool that produced this result"
    )
    session_id: Optional[str] = Field(
        default=None, description="ID of the session that produced this result"
    )
    
    # Add these fields to match ToolResultMetadata expectations
    start_time: Optional[datetime] = Field(
        default_factory=datetime.now, description="Time when execution started"
    )
    end_time: Optional[datetime] = Field(
        default=None, description="Time when execution completed"
    )
    execution_time_ms: Optional[float] = Field(
        default=None, description="Execution time in milliseconds"
    )
    execution_id: Optional[str] = Field(
        default=None, description="Unique identifier for this execution"
    )


class SearchResponse(ToolResult):
    """Structured response from the web search tool, inheriting ToolResult."""

    query: str = Field(description="The search query that was executed")
    results: List[SearchResult] = Field(default_factory=list, description="List of search results")
    metadata: Optional[SearchMetadata] = Field(
        default=None, description="Metadata about the search"
    )

    @model_validator(mode="after")
    def populate_output(self) -> "SearchResponse":
        """Populate output or error fields based on search results."""
        if self.error:
            return self

        result_text = [f"Search results for '{self.query}':"]

        for i, result in enumerate(self.results, 1):
            # Add title with position number
            title = result.title.strip() or "No title"
            result_text.append(f"\n{i}. {title}")

            # Add URL with proper indentation
            result_text.append(f"   URL: {result.url}")

            # Add description if available
            if result.description and result.description.strip():
                desc = result.description.strip()
                # Truncate long descriptions
                if len(desc) > 300:
                    desc = desc[:297] + "..."
                result_text.append(f"   Description: {desc}")

            # Add content preview if available
            if result.raw_content:
                content_preview = result.raw_content[:500].replace("\n", " ").strip()
                if len(result.raw_content) > 500:
                    content_preview += "..."
                result_text.append(f"   Content Preview: {content_preview}")

        # Add metadata at the bottom if available
        if self.metadata:
            result_text.extend(
                [
                    "\nMetadata:",
                    f"- Total results: {self.metadata.total_results}",
                    f"- Language: {self.metadata.language}",
                    f"- Country: {self.metadata.country}",
                    f"- Time taken: {self.metadata.time_taken:.2f} seconds",
                    f"- Engines tried: {', '.join(self.metadata.engines_tried)}",
                ]
            )

        self.output = "\n".join(result_text)
        return self


class RateLimiter:
    """Rate limiter to prevent hitting API rate limits."""

    def __init__(
        self, rate_limit: int = DEFAULT_RATE_LIMIT, period: int = DEFAULT_RATE_LIMIT_PERIOD
    ):
        """
        Initialize rate limiter.

        Args:
            rate_limit: Maximum requests per second
            period: Time period in seconds for rate limiting
        """
        self.rate_limit = rate_limit
        self.period = period
        self.request_times: List[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request, waiting if necessary.

        Raises:
            asyncio.TimeoutError: If wait time exceeds limit
        """
        async with self.lock:
            now = time.time()

            # Remove old timestamps
            self.request_times = [t for t in self.request_times if now - t < self.period]

            # Check if we're at the limit
            if len(self.request_times) >= self.rate_limit:
                # Calculate wait time
                oldest = min(self.request_times)
                wait_time = self.period - (now - oldest)
                if wait_time > 0:
                    logger.debug(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time)

            # Add current time and allow request
            self.request_times.append(time.time())


class WebContentFetcher:
    """Utility class for fetching web content."""

    def __init__(self) -> None:
        """Initialize the content fetcher with rate limiter."""
        rate_limit = get_config("search.rate_limit", DEFAULT_RATE_LIMIT)
        period = get_config("search.rate_limit_period", DEFAULT_RATE_LIMIT_PERIOD)
        self.rate_limiter = RateLimiter(rate_limit, period)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    async def fetch_content(self, url: str, timeout: int = 10) -> Optional[str]:
        """
        Fetch and extract the main content from a webpage.

        Args:
            url: The URL to fetch content from
            timeout: Request timeout in seconds

        Returns:
            Extracted text content or None if fetching fails
        """
        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"Invalid URL: {url}")
                return None
        except Exception:
            logger.warning(f"Could not parse URL: {url}")
            return None

        try:
            # Wait for rate limiter
            await self.rate_limiter.acquire()
            logger.debug(f"Fetching content from: {url}")

            # Use asyncio to run requests in a thread pool
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.session.get(url, timeout=timeout)
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch content from {url}: HTTP {response.status_code}")
                return None

            # Get content type from headers
            content_type = response.headers.get("Content-Type", "").lower()

            # Skip non-text content
            if "text/html" not in content_type and "text/" not in content_type:
                logger.debug(f"Skipping non-text content: {content_type} for {url}")
                return None

            # Try different parsers in case of failure
            parsers = ["html.parser", "lxml", "html5lib"]
            extracted_text = None

            for parser in parsers:
                try:
                    # Parse HTML with BeautifulSoup
                    soup = BeautifulSoup(response.text, parser)

                    # Remove script and style elements
                    for tag in soup(
                        ["script", "style", "header", "footer", "nav", "iframe", "meta", "link"]
                    ):
                        tag.decompose()

                    # Get text content
                    text = soup.get_text(separator="\n", strip=True)

                    # Clean up whitespace
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    extracted_text = "\n".join(lines)

                    # If we got content, break the loop
                    if extracted_text:
                        break
                except Exception as e:
                    logger.debug(f"Parser {parser} failed: {e}")
                    continue

            # Final check and limit size (100KB max)
            if not extracted_text:
                logger.warning(f"Could not extract text from {url}")
                return None

            logger.debug(f"Successfully extracted content from {url} ({len(extracted_text)} chars)")
            return extracted_text[:100000]  # Limit to 100KB

        except Exception as e:
            logger.warning(f"Error fetching content from {url}: {e}")
            return None


@register_tool(category="research")
class WebSearch(BaseTool):
    """
    Search the web for real-time information using multiple search engines.

    Key capabilities:
    * Query multiple search engines including Google, Bing, DuckDuckGo, and Baidu
    * Retrieve search results with URLs, titles, and descriptions
    * Fetch and extract content from search result pages
    * Automatic fallback to alternative engines if primary fails
    * Support for language and country-specific searches
    * Configurable number of results and search engine preference

    Use this tool when:
    * You need to find current information on the web
    * You need to research facts, data, or content online
    * You need to gather information from multiple sources
    * You need the actual content of web pages for analysis
    * You want to search across different regions or languages

    Notes:
    * Results are automatically cached to prevent duplicate searches
    * Content fetching has rate limiting to prevent overloading sites
    * Search engines are tried in order of preference until successful
    * Large responses are automatically truncated for readability
    """

    name: str = "web_search"
    description: str = """
    Search the web for real-time information using multiple search engines.
    
    * Purpose: Find current information from the web using multiple search engines
    * Usage: Provide a search query and optional parameters to control results
    * Features: Multi-engine search, content fetching, automatic fallback
    * Returns: Structured search results with URLs, titles, descriptions, and optional content
    
    The tool automatically tries multiple search engines if the primary one fails,
    and can optionally fetch and extract the main content from search result pages.
    Results include standardized metadata regardless of which engine provided them.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The search query to submit to the search engine.",
            },
            "num_results": {
                "type": "integer",
                "description": "(optional) The number of search results to return. Default is 5.",
                "default": 5,
            },
            "lang": {
                "type": "string",
                "description": "(optional) Language code for search results (default: en).",
                "default": "en",
            },
            "country": {
                "type": "string",
                "description": "(optional) Country code for search results (default: us).",
                "default": "us",
            },
            "fetch_content": {
                "type": "boolean",
                "description": "(optional) Whether to fetch full content from result pages. Default is false.",
                "default": False,
            },
            "search_engine": {
                "type": "string",
                "description": "(optional) Specify search engine to use. Options: google, bing, duckduckgo, baidu, or auto.",
                "enum": ["google", "bing", "duckduckgo", "baidu", "auto"],
                "default": "auto",
            },
        },
        "required": ["query"],
    }

    capabilities: Set[Union[str, ToolCapability]] = {
        ToolCapability.SEARCH,
        ToolCapability.NETWORK_ACCESS,
    }

    # define attributes that will be set
    search_engines: Dict[str, Any] = Field(default_factory=dict, exclude=True)
    content_fetcher: Optional[Any] = Field(default=None, exclude=True)
    results_cache: Dict[str, Any] = Field(default_factory=dict, exclude=True)
    cache_expiry: int = Field(default=300, description="Cache expiry time in seconds") 

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the WebSearch tool with standard parameters.

        Args:
            name: Override for tool name
            description: Override for tool description
            parameters: Override for tool parameters schema
            config: Tool configuration settings
            **kwargs: Additional keyword arguments
        """
        # Access class field info directly from the model fields
        model_fields = self.__class__.model_fields
        
        # Initialize with parent class first, using field info to get defaults
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            **kwargs
        )

        # Then initialize other instance attributes
        self.config = config or ToolConfig(
            timeout=60.0,  # Default timeout for search operations
            max_retries=3,  # Search can be retried
            cache_results=True,  # Cache search results
        )

        # Initialize components (as regular attributes, not fields)
        self.search_engines = {}
        self.content_fetcher = None
        self.results_cache = {}
        self.cache_expiry = get_config("search.cache_expiry", 300)  # 5 minutes by default

        logger.debug("WebSearch tool initialized")

    async def initialize(self, **kwargs: Any) -> bool:
        """
        Initialize search engines and content fetcher.

        Args:
            **kwargs: Additional initialization parameters

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            # Initialize search engines
            self._initialize_search_engines()

            # Create content fetcher
            self.content_fetcher = WebContentFetcher()

            logger.info("WebSearch tool successfully initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize WebSearch tool: {e}")
            return False

    def _initialize_search_engines(self) -> None:
        """Initialize available search engines with proper error handling."""
        engines_to_init = [
            ("google", GoogleSearchEngine),
            ("bing", BingSearchEngine),
            ("duckduckgo", DuckDuckGoSearchEngine),
            ("baidu", BaiduSearchEngine),
        ]

        for name, engine_class in engines_to_init:
            try:
                self.search_engines[name] = engine_class()
                logger.debug(f"Initialized search engine: {name}")
            except Exception as e:
                logger.warning(f"Failed to initialize {name} search engine: {e}")

    async def execute(self, **kwargs: Any) -> SearchResponse:
        """
        Execute a Web search and return detailed search results.

        Args:
            **kwargs: Keyword arguments including:
                query: The search query to submit to the search engine
                num_results: The number of search results to return (default: 5)
                lang: Language code for search results
                country: Country code for search results
                fetch_content: Whether to fetch content from result pages (default: False)
                search_engine: Specific search engine to use

        Returns:
            A structured response containing search results and metadata
        """
        start_time = time.time()

        # Use timeout from config if available
        timeout = getattr(self.config, "timeout", None)

        # Extract parameters from kwargs
        try:
            query = kwargs.get("query")
            if not query:
                logger.error("Missing required 'query' parameter")
                return SearchResponse(query="", error="Query parameter is required", results=[])

            # Extract and validate other parameters
            num_results = int(kwargs.get("num_results", 5))
            lang = kwargs.get("lang")
            country = kwargs.get("country")
            fetch_content = kwargs.get("fetch_content", False)
            search_engine = kwargs.get("search_engine", "auto")

            # Use config values for lang and country if not specified
            if lang is None:
                lang = get_config("search.lang", "en")

            if country is None:
                country = get_config("search.country", "us")

            logger.info(f"Executing web search for query: {query}")
            logger.debug(
                f"Parameters: num_results={num_results}, lang={lang}, country={country}, fetch_content={fetch_content}, search_engine={search_engine}"
            )

            # Initialize engines if needed
            if not self.search_engines:
                self._initialize_search_engines()

            # Initialize content fetcher if needed
            if fetch_content and self.content_fetcher is None:
                self.content_fetcher = WebContentFetcher()

            # Check cache for existing results
            cache_key = f"{query}:{num_results}:{lang}:{country}:{fetch_content}"
            cached_result = self._check_cache(cache_key)
            if cached_result:
                logger.info(f"Using cached results for query: {query}")
                return cached_result

            search_params = {"lang": lang, "country": country}

            # Determine engines to try
            engines_tried = []

            if search_engine != "auto":
                if search_engine in self.search_engines:
                    engines_to_try = [search_engine]
                else:
                    logger.warning(f"Specified search engine '{search_engine}' is not available")
                    return SearchResponse(
                        query=query,
                        error=f"Specified search engine '{search_engine}' is not available.",
                        results=[],
                    )
            else:
                engines_to_try = self._get_engine_order()

            # Perform search with each engine until successful
            results = []
            for engine_name in engines_to_try:
                engines_tried.append(engine_name)
                if engine_name not in self.search_engines:
                    logger.warning(f"Search engine {engine_name} not available, skipping.")
                    continue

                logger.info(f"Attempting search with {engine_name.capitalize()}")

                try:
                    engine = self.search_engines[engine_name]
                    search_items = await self._perform_search_with_engine(
                        engine, query, num_results, search_params
                    )

                    if search_items:
                        # Transform search items into structured results
                        results = [
                            SearchResult(
                                position=i + 1,
                                url=item.url,
                                title=item.title or f"Result {i + 1}",
                                description=item.description or "",
                                source=engine_name,
                            )
                            for i, item in enumerate(search_items)
                        ]
                        logger.info(
                            f"Search with {engine_name} successful, found {len(results)} results"
                        )
                        break
                except Exception as e:
                    logger.error(f"Error with {engine_name} search engine: {str(e)}")
                    continue

            # Return early if no results found
            if not results:
                logger.warning(
                    f"No results found with any search engine. Tried: {', '.join(engines_tried)}"
                )
                return SearchResponse(
                    query=query,
                    error=f"No results found with any search engine. Tried: {', '.join(engines_tried)}",
                    results=[],
                    metadata=SearchMetadata(
                        total_results=0,
                        language=lang,
                        country=country,
                        time_taken=time.time() - start_time,
                        engines_tried=engines_tried,
                    ),
                )

            # Fetch content if requested
            if fetch_content:
                logger.debug(f"Fetching content for {len(results)} results")
                results = await self._fetch_content_for_results(results)
                logger.info(f"Content fetched for {len(results)} results")

            # Create the response
            response = SearchResponse(
                query=query,
                results=results,
                metadata=SearchMetadata(
                    total_results=len(results),
                    language=lang,
                    country=country,
                    time_taken=time.time() - start_time,
                    engines_tried=engines_tried,
                    tool_name=self.name  # Set the tool_name attribute to fix the error
                ),
            )

            # Cache the results if caching is enabled
            if getattr(self.config, "cache_results", True):
                self._update_cache(cache_key, response)
                logger.debug(f"Cached search results for: {query}")

            return response

        except ToolError as e:
            # Known errors
            logger.error(f"Tool error during search: {e}")
            return SearchResponse(query=kwargs.get("query", ""), error=str(e), results=[])
        except Exception as e:
            # Unexpected errors
            logger.error(f"Unexpected error in web search: {str(e)}", exc_info=True)
            return SearchResponse(
                query=kwargs.get("query", ""),
                error=f"An unexpected error occurred: {str(e)}",
                results=[],
            )

    def _check_cache(self, cache_key: str) -> Optional[SearchResponse]:
        """
        Check if results are in cache and not expired.

        Args:
            cache_key: Cache key to check

        Returns:
            Cached response if available, None otherwise
        """
        if cache_key in self.results_cache:
            entry = self.results_cache[cache_key]
            if time.time() - entry["timestamp"] < self.cache_expiry:
                return cast(SearchResponse, entry["response"])
            else:
                # Expired entry
                del self.results_cache[cache_key]
                logger.debug(f"Removed expired cache entry: {cache_key}")
        return None

    def _update_cache(self, cache_key: str, response: SearchResponse) -> None:
        """
        Add search results to cache.

        Args:
            cache_key: Cache key to use
            response: Response to cache
        """
        self.results_cache[cache_key] = {"timestamp": time.time(), "response": response}

        # Clean expired entries
        for key in list(self.results_cache.keys()):
            if time.time() - self.results_cache[key]["timestamp"] > self.cache_expiry:
                del self.results_cache[key]

    async def _fetch_content_for_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Fetch and add web content to search results.

        Args:
            results: Search results to fetch content for

        Returns:
            Search results with content added
        """
        if not results:
            return []

        # Ensure content fetcher is initialized
        if self.content_fetcher is None:
            self.content_fetcher = WebContentFetcher()
            logger.debug("Initialized WebContentFetcher")

        # Create tasks for each result
        tasks = [self._fetch_single_result_content(result) for result in results]
        logger.debug(f"Created {len(tasks)} content fetch tasks")

        # Execute all fetch operations concurrently
        fetched_results = await asyncio.gather(*tasks)
        return list(fetched_results)

    async def _fetch_single_result_content(self, result: SearchResult) -> SearchResult:
        """
        Fetch content for a single search result.

        Args:
            result: Search result to fetch content for

        Returns:
            Search result with content added
        """
        if result.url:
            logger.debug(f"Fetching content for URL: {result.url}")
            # Ensure content fetcher is initialized
            if self.content_fetcher is None:
                self.content_fetcher = WebContentFetcher()

            content = await self.content_fetcher.fetch_content(result.url)
            if content:
                # Create a new result with content added
                logger.debug(f"Content fetched successfully for: {result.url}")
                return SearchResult(
                    position=result.position,
                    url=result.url,
                    title=result.title,
                    description=result.description,
                    source=result.source,
                    raw_content=content,
                )
        return result

    def _get_engine_order(self) -> List[str]:
        """
        Determines the order in which to try search engines.

        Returns:
            List of engines to try in order
        """
        preferred = get_config("search.engine", "google").lower()
        fallbacks = get_config("search.fallback_engines", [])

        if isinstance(fallbacks, str):
            fallbacks = [fallbacks]

        # Start with preferred engine, then fallbacks, then remaining engines
        engine_order = [preferred] if preferred in self.search_engines else []
        engine_order.extend(
            [fb for fb in fallbacks if fb in self.search_engines and fb not in engine_order]
        )
        engine_order.extend([e for e in self.search_engines if e not in engine_order])

        logger.debug(f"Search engine order: {engine_order}")
        return engine_order

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, TimeoutError)),
    )
    async def _perform_search_with_engine(
        self,
        engine: WebSearchEngine,
        query: str,
        num_results: int,
        search_params: Dict[str, str],
    ) -> List[SearchItem]:
        """
        Execute search with the given engine and parameters.

        Args:
            engine: Search engine to use
            query: Search query
            num_results: Number of results to retrieve
            search_params: Additional search parameters

        Returns:
            List of search results

        Raises:
            Exception: If search fails
        """
        try:
            # Create a lambda to execute the synchronous search in a separate thread
            loop = asyncio.get_event_loop()
            logger.debug(f"Executing search for: {query}")
            return await loop.run_in_executor(
                None,
                lambda: list(
                    engine.perform_search(
                        query,
                        num_results=num_results,
                        lang=search_params.get("lang"),
                        country=search_params.get("country"),
                    )
                ),
            )
        except Exception as e:
            logger.error(f"Error performing search with engine: {e}")
            raise  # Let the retry decorator handle it

    async def cleanup(self) -> None:
        """Clean up resources used by the web search tool."""
        logger.info("Cleaning up web search resources")

        # Clear cache to free memory
        self.results_cache.clear()

        # Close any session in content fetcher
        if self.content_fetcher and hasattr(self.content_fetcher, "session"):
            try:
                self.content_fetcher.session.close()
                logger.debug("Content fetcher session closed")
            except Exception as e:
                logger.warning(f"Error closing content fetcher session: {e}")
