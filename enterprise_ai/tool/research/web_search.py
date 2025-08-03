"""Web search tool for Enterprise AI."""

import asyncio
import time
from typing import Any, Dict, List, Optional, Set, Union, cast
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from enterprise_ai.defaults import (
    DEFAULT_RESEARCH_RESULTS_PER_SEARCH,
    get_config_value
)
from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, ToolResultMetadata  # Using unified ToolResult
from enterprise_ai.logger import ToolExecutionContext
from enterprise_ai.tool.research.search import (
    BaiduSearchEngine,
    BingSearchEngine,
    DuckDuckGoSearchEngine,
    GoogleSearchEngine,
    SearchItem,
    WebSearchEngine,
)

logger = get_optimized_logger("tool.research.web_search")

# Rate limiting settings
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
    snippet: str = Field(default="", description="Snippet of the search result")  # Added for compatibility
    source: str = Field(description="The search engine that provided this result")
    raw_content: Optional[str] = Field(
        default=None, description="Raw content from the search result page if available"
    )

    def __str__(self) -> str:
        """String representation of a search result."""
        return f"{self.title} ({self.url})"

    @model_validator(mode="after")
    def sync_description_snippet(self) -> "SearchResult":
        """Ensure description and snippet are synchronized for compatibility."""
        if not self.snippet and self.description:
            self.snippet = self.description
        elif not self.description and self.snippet:
            self.description = self.snippet
        return self

class SearchMetadata(ToolResultMetadata):
    """Metadata about the search operation."""

    total_results: int = Field(description="Total number of results found")
    language: str = Field(description="Language code used for the search")
    country: str = Field(description="Country code used for the search")
    time_taken: float = Field(default=0.0, description="Time taken for the search in seconds")
    engines_tried: List[str] = Field(
        default_factory=list, description="Search engines that were tried"
    )

class SearchResponse(ToolResult):
    """Structured response from the web search tool using unified ToolResult."""

    query: str = Field(description="The search query that was executed")
    results: List[SearchResult] = Field(default_factory=list, description="List of search results")
    search_metadata: Optional[SearchMetadata] = Field(
        default=None, description="Search-specific metadata"
    )

    def __init__(self, **data: Any) -> None:
        # Extract data for result formatting
        query = data.get("query", "")
        results = data.get("results", [])
        search_metadata = data.get("search_metadata", None)
        
        # Generate result text BEFORE calling parent constructor
        result_text = self._format_search_results_static(query, results, search_metadata)
        
        # Set required fields for parent constructor
        data["result"] = result_text
        data["tool_call_id"] = data.get("tool_call_id", "")
        data["name"] = data.get("name", "web_search")
        data["success"] = not bool(data.get("error"))
        
        # Now call parent constructor with all required fields
        super().__init__(**data)

    @staticmethod
    def _format_search_results_static(
        query: str, 
        results: List[SearchResult], 
        search_metadata: Optional[SearchMetadata] = None
    ) -> str:
        """Static method to format search results for display."""
        if not results:
            return f"No search results found for '{query}'"

        result_text = [f"Search results for '{query}':"]

        for i, result in enumerate(results, 1):
            title = result.title.strip() or "No title"
            result_text.append(f"\n{i}. {title}")
            result_text.append(f"   URL: {result.url}")

            if result.description and result.description.strip():
                desc = result.description.strip()
                if len(desc) > 300:
                    desc = desc[:297] + "..."
                result_text.append(f"   Description: {desc}")

            if result.raw_content:
                content_preview = result.raw_content[:500].replace("\n", " ").strip()
                if len(result.raw_content) > 500:
                    content_preview += "..."
                result_text.append(f"   Content Preview: {content_preview}")

        # Add metadata if available
        if search_metadata:
            result_text.extend([
                "\nMetadata:",
                f"- Total results: {search_metadata.total_results}",
                f"- Language: {search_metadata.language}",
                f"- Country: {search_metadata.country}",
                f"- Time taken: {search_metadata.time_taken:.2f} seconds",
                f"- Engines tried: {', '.join(search_metadata.engines_tried)}",
            ])

        return "\n".join(result_text)

    def _format_search_results(self, query: str, results: List[SearchResult]) -> str:
        """Instance method that delegates to static method for backward compatibility."""
        return self._format_search_results_static(query, results, self.search_metadata)

    @property
    def output(self) -> str:
        """Backward compatibility property."""
        return self.result

class RateLimiter:
    """Rate limiter to prevent hitting API rate limits."""

    def __init__(self, rate_limit: int = DEFAULT_RATE_LIMIT, period: int = DEFAULT_RATE_LIMIT_PERIOD):
        self.rate_limit = rate_limit
        self.period = period
        self.request_times: List[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission to make a request, waiting if necessary."""
        async with self.lock:
            now = time.time()
            self.request_times = [t for t in self.request_times if now - t < self.period]

            if len(self.request_times) >= self.rate_limit:
                oldest = min(self.request_times)
                wait_time = self.period - (now - oldest)
                if wait_time > 0:
                    logger.debug("Rate limit reached, waiting %.2fs seconds", wait_time)
                    await asyncio.sleep(wait_time)

            self.request_times.append(time.time())

class WebContentFetcher:
    """Utility class for fetching web content with optimized extraction."""

    def __init__(self) -> None:
        rate_limit = get_config_value("search.rate_limit", DEFAULT_RATE_LIMIT)
        period = get_config_value("search.rate_limit_period", DEFAULT_RATE_LIMIT_PERIOD)
        self.rate_limiter = RateLimiter(rate_limit, period)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        
        # Lazy load optimized content extractor
        self._content_extractor = None
        self._extraction_method = None

    def _get_content_extractor(self):
        """Lazy load the optimized content extractor."""
        if self._content_extractor is None:
            try:
                # Try to use the optimized modular extraction system
                from enterprise_ai.tool.research.content_extractor import EnterpriseContentExtractor
                self._content_extractor = EnterpriseContentExtractor(
                    timeout=15,  # Fast timeout for web search
                    enable_js_extraction=False  # Disable slow methods for search
                )
                self._extraction_method = "optimized"
                logger.info("Using optimized content extraction for web search")
            except ImportError as e:
                logger.warning(f"Optimized extractor not available ({e}), using basic extraction")
                self._extraction_method = "basic"
        
        return self._content_extractor

    async def fetch_content(self, url: str, timeout: int = 10) -> Optional[str]:
        """Fetch and extract content using optimized extraction with fallback."""
        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning("Invalid URL: %s", url)
                return None
        except Exception:
            logger.warning("Could not parse URL: %s", url)
            return None

        await self.rate_limiter.acquire()
        logger.debug("Fetching content from: %s", url)

        # Try optimized extraction first
        extractor = self._get_content_extractor()
        if extractor and self._extraction_method == "optimized":
            try:
                result = await extractor.extract(url)
                if result.success and result.content:
                    logger.debug(f"Optimized extraction success: {len(result.content)} chars via {result.method}")
                    return result.content[:100000]  # Limit to 100KB
                else:
                    logger.debug(f"Optimized extraction failed: {result.error}, falling back to basic")
            except Exception as e:
                logger.debug(f"Optimized extraction error: {e}, falling back to basic")

        # Fallback to basic extraction
        return await self._fetch_content_basic(url, timeout)

    async def _fetch_content_basic(self, url: str, timeout: int = 10) -> Optional[str]:
        """Basic content extraction using BeautifulSoup (fallback)."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.session.get(url, timeout=timeout)
            )

            if response.status_code != 200:
                logger.warning("Failed to fetch content from %s: HTTP %s", url, response.status_code)
                return None

            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type and "text/" not in content_type:
                logger.debug("Skipping non-text content: %s for %s", content_type, url)
                return None

            # Try different parsers in case of failure
            parsers = ["html.parser", "lxml", "html5lib"]
            extracted_text = None

            for parser in parsers:
                try:
                    soup = BeautifulSoup(response.text, parser)
                    for tag in soup(["script", "style", "header", "footer", "nav", "iframe", "meta", "link"]):
                        tag.decompose()

                    text = soup.get_text(separator="\n", strip=True)
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    extracted_text = "\n".join(lines)

                    if extracted_text:
                        break
                except Exception as e:
                    logger.debug("Parser %s failed: %s", parser, e)
                    continue

            if not extracted_text:
                logger.warning("Could not extract text from %s", url)
                return None

            logger.debug("Basic extraction success: %s chars", len(extracted_text))
            return extracted_text[:100000]  # Limit to 100KB

        except Exception as e:
            logger.warning("Error fetching content from %s: %s", url, e)
            return None

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
    short_description: str = "Search for current information on the web like news, articles, and facts. For internet searches only."
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

    # Tool attributes (not Pydantic fields)
    search_engines: Dict[str, Any] = Field(default_factory=dict, exclude=True)
    content_fetcher: Optional[WebContentFetcher] = Field(default=None, exclude=True)
    results_cache: Dict[str, Any] = Field(default_factory=dict, exclude=True)
    cache_expiry: int = Field(default=300, exclude=True)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the WebSearch tool with standard parameters."""
        model_fields = self.__class__.model_fields

        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            **kwargs,
        )

        self.config = config or ToolConfig(
            timeout=60.0,
            max_retries=3,
            cache_results=True,
        )

        # Initialize components
        self.search_engines = {}
        self.content_fetcher = None
        self.results_cache = {}
        self.cache_expiry = get_config_value("search.cache_expiry", 300)

        logger.debug("WebSearch tool initialized")

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize search engines and content fetcher."""
        try:
            self._initialize_search_engines()
            self.content_fetcher = WebContentFetcher()
            return True
        except Exception as e:
            logger.error("Failed to initialize WebSearch tool: %s", e)
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
                logger.debug("Initialized search engine: %s", name)
            except Exception as e:
                logger.warning("Failed to initialize %s search engine: %s", name, e)

    async def execute(self, **kwargs: Any) -> SearchResponse:
        """Execute a Web search with smart source tracking."""
        
        # Extract parameters
        query = kwargs.get("query")
        if not query:
            logger.error("Missing required 'query' parameter")
            return SearchResponse(
                query="",
                results=[],
                error="Query parameter is required",
                tool_call_id="",
                name=self.name
            )

        num_results = int(kwargs.get("num_results", 5))
        lang = kwargs.get("lang") or get_config_value("search.lang", "en")
        country = kwargs.get("country") or get_config_value("search.country", "us")
        fetch_content = kwargs.get("fetch_content", False)
        search_engine = kwargs.get("search_engine", "auto")
        
        # START SMART LOGGING - Wrap execution in context
        with ToolExecutionContext("web_search") as ctx:
            try:
                # Initialize engines if needed
                if not self.search_engines:
                    self._initialize_search_engines()

                if fetch_content and self.content_fetcher is None:
                    self.content_fetcher = WebContentFetcher()

                # Check cache (existing logic)
                cache_key = f"{query}:{num_results}:{lang}:{country}:{fetch_content}"
                cached_result = self._check_cache(cache_key)
                if cached_result:
                    logger.info("🔍 Using cached results for query: %s", query)
                    return cached_result

                # Determine engines to try
                engines_tried = []
                if search_engine != "auto":
                    if search_engine in self.search_engines:
                        engines_to_try = [search_engine]
                    else:
                        logger.warning("Specified search engine '%s' is not available", search_engine)
                        return SearchResponse(
                            query=query,
                            results=[],
                            error=f"Specified search engine '{search_engine}' is not available.",
                            tool_call_id="",
                            name=self.name
                        )
                else:
                    engines_to_try = self._get_engine_order()

                # Perform search
                search_params = {"lang": lang, "country": country}
                search_results = []

                for engine_name in engines_to_try:
                    engines_tried.append(engine_name)
                    if engine_name not in self.search_engines:
                        logger.warning("Search engine %s not available, skipping.", engine_name)
                        continue

                    try:
                        engine = self.search_engines[engine_name]
                        search_items = await self._perform_search_with_engine(
                            engine, query, num_results, search_params
                        )

                        if search_items:
                            search_results = [
                                SearchResult(
                                    position=i + 1,
                                    url=item.url,
                                    title=item.title or f"Result {i + 1}",
                                    description=item.description or "",
                                    source=engine_name,
                                )
                                for i, item in enumerate(search_items)
                            ]
                            break
                    except Exception as e:
                        logger.error("Error with %s search engine: %s", engine_name, str(e))
                        continue

                if not search_results:
                    logger.warning("No results found with any search engine. Tried: %s", ', '.join(engines_tried))
                    return SearchResponse(
                        query=query,
                        results=[],
                        error=f"No results found with any search engine. Tried: {', '.join(engines_tried)}",
                        tool_call_id="",
                        name=self.name
                    )

                # SMART CONTENT FETCHING - Only log sources we actually extract from
                processed_results = []
                successful_extractions = 0
                
                for result in search_results:
                    processed_result = SearchResult(
                        position=result.position,
                        url=result.url,
                        title=result.title,
                        description=result.description,
                        source=result.source,
                        raw_content=None
                    )
                    
                    # Try to fetch content if requested
                    if fetch_content and self.content_fetcher:
                        try:
                            content = await self.content_fetcher.fetch_content(result.url)
                            
                            if content and len(content.strip()) > 100:  # Minimum viable content
                                # Calculate quality score
                                quality_score = self._calculate_content_quality(content)
                                
                                # ONLY LOG IF WE SUCCESSFULLY EXTRACTED USEFUL CONTENT
                                if quality_score > 0.3:  # Threshold for "useful"
                                    ctx.add_source(
                                        url=result.url,
                                        content_length=len(content),
                                        extraction_method=getattr(self.content_fetcher, '_extraction_method', 'web_parser'),
                                        success_score=quality_score,
                                        search_engine=result.source,
                                        result_position=result.position,
                                        query=query
                                    )
                                    
                                    processed_result.raw_content = content
                                    successful_extractions += 1
                                    
                        except Exception as e:
                            logger.debug(f"Failed to extract content from {result.url}: {e}")
                            # Don't log failed extractions - this is the key improvement!
                    
                    processed_results.append(processed_result)

                # Track insights (successful extractions)
                ctx.add_insights(successful_extractions)

                # Create response
                response = SearchResponse(
                    query=query,
                    results=processed_results,
                    tool_call_id="",
                    name=self.name,
                    search_metadata=SearchMetadata(
                        total_results=len(processed_results),
                        language=lang,
                        country=country,
                        time_taken=ctx.start_time and (time.time() - ctx.start_time.timestamp()) or 0,
                        engines_tried=engines_tried,
                        tool_name=self.name,
                    ),
                )
                
                # Cache results
                if getattr(self.config, "cache_results", True):
                    self._update_cache(cache_key, response)

                # SMART LOGGING SUMMARY (instead of verbose logs)
                logger.info(
                    f"🔍 Search complete: {query} | "
                    f"{len(processed_results)} results | "
                    f"{successful_extractions} sources extracted"
                )
                
                return response
                
            except Exception as e:
                # Error will be automatically logged by context manager
                logger.error(f"Search failed: {str(e)}")
                return SearchResponse(
                    query=query,
                    results=[],
                    error=f"Search failed: {str(e)}",
                    tool_call_id="",
                    name=self.name
                )

    def _check_cache(self, cache_key: str) -> Optional[SearchResponse]:
        """Check if results are in cache and not expired."""
        if cache_key in self.results_cache:
            entry = self.results_cache[cache_key]
            if time.time() - entry["timestamp"] < self.cache_expiry:
                return cast(SearchResponse, entry["response"])
            else:
                del self.results_cache[cache_key]
                logger.debug("Removed expired cache entry: %s", cache_key)
        return None

    def _update_cache(self, cache_key: str, response: SearchResponse) -> None:
        """Add search results to cache."""
        self.results_cache[cache_key] = {"timestamp": time.time(), "response": response}

        # Clean expired entries
        for key in list(self.results_cache.keys()):
            if time.time() - self.results_cache[key]["timestamp"] > self.cache_expiry:
                del self.results_cache[key]

    async def _fetch_content_for_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Fetch and add web content to search results."""
        if not results or self.content_fetcher is None:
            return results

        tasks = [self._fetch_single_result_content(result) for result in results]
        logger.debug("Created %s content fetch tasks", len(tasks))
        fetched_results = await asyncio.gather(*tasks)
        return list(fetched_results)

    async def _fetch_single_result_content(self, result: SearchResult) -> SearchResult:
        """Fetch content for a single search result."""
        if result.url and self.content_fetcher is not None:
            logger.debug("Fetching content for URL: %s", result.url)
            content = await self.content_fetcher.fetch_content(result.url)
            if content:
                logger.debug("Content fetched successfully for: %s", result.url)
                return SearchResult(
                    position=result.position,
                    url=result.url,
                    title=result.title,
                    description=result.description,
                    source=result.source,
                    raw_content=content,
                )
        return result
    
    def _calculate_content_quality(self, content: str) -> float:
        """
        Calculate quality score for extracted content.
        
        This helps determine if a source is worth logging.
        """
        if not content or len(content.strip()) < 50:
            return 0.0
        
        # Basic quality heuristics
        content_length = len(content.strip())
        word_count = len(content.split())
        
        # Length score (0-0.4)
        length_score = min(0.4, content_length / 2000)
        
        # Word count score (0-0.3)  
        word_score = min(0.3, word_count / 300)
        
        # Structure score (0-0.3) - check for paragraphs, sentences
        structure_score = 0.0
        if '\n' in content:
            structure_score += 0.1
        if '.' in content and content.count('.') > 2:
            structure_score += 0.1
        if any(marker in content.lower() for marker in ['http', 'www', '@']):
            structure_score += 0.1
            
        total_score = length_score + word_score + structure_score
        
        # Penalize very short or very repetitive content
        if content_length < 100:
            total_score *= 0.5
        
        unique_words = len(set(content.lower().split()))
        if unique_words < word_count * 0.3:  # Too repetitive
            total_score *= 0.7
            
        return min(1.0, total_score)

    def _get_engine_order(self) -> List[str]:
        """Determines the order in which to try search engines."""
        preferred = get_config_value("search.engine", "google").lower()
        fallbacks = get_config_value("search.fallback_engines", [])

        if isinstance(fallbacks, str):
            fallbacks = [fallbacks]

        engine_order = [preferred] if preferred in self.search_engines else []
        engine_order.extend([fb for fb in fallbacks if fb in self.search_engines and fb not in engine_order])
        engine_order.extend([e for e in self.search_engines if e not in engine_order])

        logger.debug("Search engine order: %s", engine_order)
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
        """Execute search with the given engine and parameters."""
        try:
            loop = asyncio.get_event_loop()
            logger.debug("Executing search for: %s", query)
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
            logger.error("Error performing search with engine: %s", e)
            raise

    async def cleanup(self) -> None:
        """Clean up resources used by the web search tool."""
        logger.info("Cleaning up web search resources")

        self.results_cache.clear()

        if self.content_fetcher and hasattr(self.content_fetcher, "session"):
            try:
                self.content_fetcher.session.close()
                logger.debug("Content fetcher session closed")
            except Exception as e:
                logger.warning("Error closing content fetcher session: %s", e)