"""Web search tool for Enterprise AI."""

import asyncio
import base64
import time
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from enterprise_ai.config import get_config
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.core.base import BaseTool, ToolError
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
    engines_tried: List[str] = Field(default_factory=list, description="Search engines that were tried")


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

    def __init__(self, rate_limit: int = DEFAULT_RATE_LIMIT, period: int = DEFAULT_RATE_LIMIT_PERIOD):
        """Initialize rate limiter.

        Args:
            rate_limit: Maximum requests per second
            period: Time period in seconds for rate limiting
        """
        self.rate_limit = rate_limit
        self.period = period
        self.request_times: List[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission to make a request, waiting if necessary."""
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

    def __init__(self):
        """Initialize the content fetcher with rate limiter."""
        rate_limit = get_config("search.rate_limit", DEFAULT_RATE_LIMIT)
        period = get_config("search.rate_limit_period", DEFAULT_RATE_LIMIT_PERIOD)
        self.rate_limiter = RateLimiter(rate_limit, period)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

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

            # Use asyncio to run requests in a thread pool
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.session.get(url, timeout=timeout)
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch content from {url}: HTTP {response.status_code}")
                return None

            # Get content type from headers
            content_type = response.headers.get('Content-Type', '').lower()

            # Skip non-text content
            if 'text/html' not in content_type and 'text/' not in content_type:
                logger.debug(f"Skipping non-text content: {content_type} for {url}")
                return None

            # Try different parsers in case of failure
            parsers = ['html.parser', 'lxml', 'html5lib']
            extracted_text = None

            for parser in parsers:
                try:
                    # Parse HTML with BeautifulSoup
                    soup = BeautifulSoup(response.text, parser)

                    # Remove script and style elements
                    for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'iframe', 'meta', 'link']):
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

            return extracted_text[:100000]  # Limit to 100KB

        except Exception as e:
            logger.warning(f"Error fetching content from {url}: {e}")
            return None


@register_tool(category="research")
class WebSearch(BaseTool):
    """Search the web for information using various search engines."""

    name: str = "web_search"
    description: str = """Search the web for real-time information about any topic.
    This tool returns comprehensive search results with relevant information, URLs, titles, and descriptions.
    If the primary search engine fails, it automatically falls back to alternative engines."""
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

    def __init__(self) -> None:
        """Initialize the WebSearch tool with search engines."""
        super().__init__(name="web_search", description=self.description, parameters=self.parameters)

        # Initialize search engines
        self._search_engines: Dict[str, WebSearchEngine] = {}
        self._initialize_search_engines()

        # Create content fetcher
        self.content_fetcher = WebContentFetcher()

        # Results cache to avoid repeated searches
        self._results_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_expiry = get_config("search.cache_expiry", 300)  # 5 minutes by default

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
                self._search_engines[name] = engine_class()
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

        # Extract parameters from kwargs
        try:
            query = kwargs.get("query")
            if not query:
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
                if search_engine in self._search_engines:
                    engines_to_try = [search_engine]
                else:
                    return SearchResponse(
                        query=query,
                        error=f"Specified search engine '{search_engine}' is not available.",
                        results=[]
                    )
            else:
                engines_to_try = self._get_engine_order()

            # Perform search with each engine until successful
            results = []
            for engine_name in engines_to_try:
                engines_tried.append(engine_name)
                if engine_name not in self._search_engines:
                    logger.warning(f"Search engine {engine_name} not available, skipping.")
                    continue

                logger.info(f"🔎 Attempting search with {engine_name.capitalize()}...")

                try:
                    engine = self._search_engines[engine_name]
                    search_items = await self._perform_search_with_engine(engine, query, num_results, search_params)

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
                        logger.info(f"Search with {engine_name} successful, found {len(results)} results")
                        break
                except Exception as e:
                    logger.error(f"Error with {engine_name} search engine: {str(e)}")
                    continue

            # Return early if no results found
            if not results:
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
                    )
                )

            # Fetch content if requested
            if fetch_content:
                results = await self._fetch_content_for_results(results)

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
                )
            )

            # Cache the results
            self._update_cache(cache_key, response)

            return response

        except ToolError as e:
            # Known errors
            return SearchResponse(query=kwargs.get("query", ""), error=str(e), results=[])
        except Exception as e:
            # Unexpected errors
            logger.error(f"Unexpected error in web search: {str(e)}", exc_info=True)
            return SearchResponse(
                query=kwargs.get("query", ""),
                error=f"An unexpected error occurred: {str(e)}",
                results=[]
            )

    def _check_cache(self, cache_key: str) -> Optional[SearchResponse]:
        """Check if results are in cache and not expired."""
        if cache_key in self._results_cache:
            entry = self._results_cache[cache_key]
            if time.time() - entry["timestamp"] < self._cache_expiry:
                return entry["response"]
            else:
                # Expired entry
                del self._results_cache[cache_key]
        return None

    def _update_cache(self, cache_key: str, response: SearchResponse) -> None:
        """Add search results to cache."""
        self._results_cache[cache_key] = {
            "timestamp": time.time(),
            "response": response
        }

        # Clean expired entries
        for key in list(self._results_cache.keys()):
            if time.time() - self._results_cache[key]["timestamp"] > self._cache_expiry:
                del self._results_cache[key]

    async def _fetch_content_for_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Fetch and add web content to search results."""
        if not results:
            return []

        # Create tasks for each result
        tasks = [self._fetch_single_result_content(result) for result in results]

        # Execute all fetch operations concurrently
        fetched_results = await asyncio.gather(*tasks)
        return list(fetched_results)

    async def _fetch_single_result_content(self, result: SearchResult) -> SearchResult:
        """Fetch content for a single search result."""
        if result.url:
            content = await self.content_fetcher.fetch_content(result.url)
            if content:
                # Create a new result with content added
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
        """Determines the order in which to try search engines."""
        preferred = get_config("search.engine", "google").lower()
        fallbacks = get_config("search.fallback_engines", [])

        if isinstance(fallbacks, str):
            fallbacks = [fallbacks]

        # Start with preferred engine, then fallbacks, then remaining engines
        engine_order = [preferred] if preferred in self._search_engines else []
        engine_order.extend(
            [fb for fb in fallbacks if fb in self._search_engines and fb not in engine_order]
        )
        engine_order.extend([e for e in self._search_engines if e not in engine_order])

        return engine_order

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, TimeoutError))
    )
    async def _perform_search_with_engine(
        self,
        engine: WebSearchEngine,
        query: str,
        num_results: int,
        search_params: Dict[str, str],
    ) -> List[SearchItem]:
        """Execute search with the given engine and parameters."""
        try:
            # Create a lambda to execute the synchronous search in a separate thread
            loop = asyncio.get_event_loop()
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
