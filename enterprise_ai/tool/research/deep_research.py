"""Deep research tool for Enterprise AI."""

import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional, Set, Union, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from enterprise_ai.exceptions import EnterpriseAIError
from enterprise_ai.llm.simple import LLM
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.tool.research.web_search import SearchResult, WebSearch

logger = get_logger("tool.research.deep_research")

# Prompts for LLM interactions
OPTIMIZE_QUERY_PROMPT = """
You are a research assistant helping to optimize a search query for web research.
Your task is to reformulate the given query to be more effective for web searches.
Make it specific, use relevant keywords, and ensure it's clear and concise.

Original query: {query}

Provide only the optimized query text without any explanation or additional formatting.
"""

EXTRACT_INSIGHTS_PROMPT = """
Analyze the following content and extract key insights related to the research query.
For each insight, assess its relevance to the query on a scale of 0.0 to 1.0.

Research query: {query}
Content to analyze:
{content}

Extract up to 3 most important insights from this content. For each insight:
1. Provide the insight content
2. Provide relevance score (0.0-1.0)
"""

GENERATE_FOLLOW_UPS_PROMPT = """
Based on the insights discovered so far, generate follow-up research queries to explore gaps or related areas.
These should help deepen our understanding of the topic.

Original query: {original_query}
Current query: {current_query}
Key insights so far:
{insights}

Generate up to 3 specific follow-up queries that would help address gaps in our current knowledge.
Each query should be concise and focused on a specific aspect of the research topic.
"""

# Constants for insight parsing
DEFAULT_RELEVANCE_SCORE = 1.0
FALLBACK_RELEVANCE_SCORE = 0.7
FALLBACK_CONTENT_LIMIT = 500
# Pattern to detect start of an insight (number., -, *, •) and capture content
INSIGHT_MARKER_PATTERN = re.compile(r"^\s*(?:\d+\.|-|\*|•)\s*(.*)")
# Pattern to detect relevance score, capturing the number (case-insensitive)
RELEVANCE_SCORE_PATTERN = re.compile(r"relevance.*?:.*?(\d\.?\d*)", re.IGNORECASE)


class ResearchInsight(BaseModel):
    """A single insight discovered during research."""

    model_config = ConfigDict(frozen=True)  # Make insights immutable

    content: str = Field(description="The insight content")
    source_url: str = Field(description="URL where this insight was found")
    source_title: Optional[str] = Field(default=None, description="Title of the source")
    relevance_score: float = Field(
        default=1.0, description="Relevance score (0.0-1.0)", ge=0.0, le=1.0
    )

    def __str__(self) -> str:
        """Format insight as string with source attribution."""
        source = self.source_title or self.source_url
        return f"{self.content} [Source: {source}]"


class ResearchContext(BaseModel):
    """Research context for tracking research progress."""

    query: str = Field(description="The original research query")
    insights: List[ResearchInsight] = Field(
        default_factory=list, description="Key insights discovered"
    )
    follow_up_queries: List[str] = Field(
        default_factory=list, description="Generated follow-up queries"
    )
    visited_urls: Set[str] = Field(default_factory=set, description="URLs visited during research")
    current_depth: int = Field(default=0, description="Current depth of research exploration", ge=0)
    max_depth: int = Field(default=2, description="Maximum depth of research to reach", ge=1)


class ResearchSummary(ToolResult):
    """Comprehensive summary of deep research results."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: str = Field(description="The original research query")
    insights: List[ResearchInsight] = Field(
        default_factory=list, description="Key insights discovered"
    )
    visited_urls: Set[str] = Field(default_factory=set, description="URLs visited during research")
    depth_reached: int = Field(default=0, description="Maximum depth of research reached", ge=0)

    @model_validator(mode="after")
    def populate_output(self) -> "ResearchSummary":
        """Populate the output field after validation."""
        # Group and sort insights by relevance
        grouped_insights: Dict[str, List[ResearchInsight]] = {
            "Key Findings": [i for i in self.insights if i.relevance_score >= 0.8],
            "Additional Information": [i for i in self.insights if 0.5 <= i.relevance_score < 0.8],
            "Supplementary Information": [i for i in self.insights if i.relevance_score < 0.5],
        }

        sections = [
            f"# Research: {self.query}\n",
            f"**Sources**: {len(self.visited_urls)} | **Depth**: {self.depth_reached + 1}\n",
        ]

        for section_title, insights in grouped_insights.items():
            if insights:
                sections.append(f"## {section_title}")
                for i, insight in enumerate(insights, 1):
                    sections.extend(
                        [
                            insight.content,
                            f"> Source: [{insight.source_title or 'Link'}]({insight.source_url})\n",
                        ]
                    )

        # Assign the formatted string to the 'output' field inherited from ToolResult
        self.output = "\n".join(sections)
        return self


@register_tool(category="research")
class DeepResearch(BaseTool):
    """
    Advanced research tool that explores topics through iterative, multi-level research.

    Key capabilities:
    * Performs comprehensive research on complex topics
    * Automatically explores topics through multiple search iterations
    * Extracts and ranks key insights by relevance
    * Generates intelligent follow-up queries to deepen research
    * Organizes findings into a structured, searchable report
    * Preserves source attribution for all discoveries

    Use this tool when:
    * You need in-depth research on a complex topic
    * You want a comprehensive exploration beyond simple search
    * You need to discover connections across multiple sources
    * You want insights organized by relevance and importance
    * You need a structured summary with source attribution

    Notes:
    * Research depth can be controlled via the max_depth parameter
    * Processing time increases with depth and results count
    * All insights include relevance scores and source attribution
    * Time limits can be set to control processing duration
    """

    name: str = "deep_research"
    description: str = """
    Performs comprehensive, multi-level research on topics through iterative web searches and content analysis.

    * Purpose: Discover in-depth information on complex topics through iterative exploration
    * Usage: Provide a research query and optional parameters to control depth and scope
    * Features: Multi-level search, insight extraction, automated follow-up generation, content analysis
    * Returns: Structured research summary with insights organized by relevance and source attribution

    The tool automatically explores topics at multiple levels, generating follow-up queries based on
    initial findings. Results are analyzed for relevance and organized into a comprehensive report
    with proper source attribution.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The research question or topic to investigate.",
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum depth of iterative research (1-5). Default is 2.",
                "default": 2,
            },
            "results_per_search": {
                "type": "integer",
                "description": "Number of search results to analyze per search (1-20). Default is 5.",
                "default": 5,
            },
            "max_insights": {
                "type": "integer",
                "description": "Maximum number of insights to return. Default is 20.",
                "default": 20,
            },
            "time_limit_seconds": {
                "type": "integer",
                "description": "Maximum execution time in seconds. Default is 120.",
                "default": 120,
            },
        },
        "required": ["query"],
    }

    # Define capabilities - use SEARCH instead of RESEARCH which doesn't exist
    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.SEARCH}

    search_tool: Optional[Any] = Field(default=None, exclude=True)
    llm: Optional[Any] = Field(default=None, exclude=True)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize DeepResearch tool with standard parameters.

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
            **kwargs,
        )

        # Store tool configuration
        self.config = config or ToolConfig(
            timeout=180.0,  # Default research timeout
            max_retries=2,  # Research can be retried
            cache_results=True,  # Cache research results
        )

        # Initialize dependent tools (now these will work properly)
        self.search_tool = None
        self.llm = None

        logger.debug("DeepResearch tool initialized")

    async def initialize(self, **kwargs: Any) -> bool:
        """
        Initialize the research tool and its dependencies.

        Args:
            **kwargs: Additional initialization parameters

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            # Initialize WebSearch tool
            self.search_tool = WebSearch()

            # Initialize LLM
            self.llm = LLM()

            logger.info("DeepResearch tool successfully initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize DeepResearch tool: {e}")
            return False

    async def execute(self, **kwargs: Any) -> ResearchSummary:
        """
        Execute deep research on the given query.

        Args:
            **kwargs: Keyword arguments including:
                query: The research question or topic
                max_depth: Maximum depth of research (1-5)
                results_per_search: Results to analyze per search
                max_insights: Maximum insights to return
                time_limit_seconds: Maximum execution time

        Returns:
            ResearchSummary with organized findings
        """
        # Extract parameters from kwargs
        query = kwargs.get("query")
        if not query:
            logger.error("Missing required 'query' parameter")
            raise ToolError("Query parameter is required")

        max_depth = kwargs.get("max_depth", 2)
        results_per_search = kwargs.get("results_per_search", 5)
        max_insights = kwargs.get("max_insights", 20)

        # Use timeout from config if available, otherwise use parameter
        config_timeout = getattr(self.config, "timeout", 120)
        time_limit_seconds = kwargs.get("time_limit_seconds", config_timeout)

        # Normalize parameters
        max_depth = max(1, min(max_depth, 5))
        results_per_search = max(1, min(results_per_search, 20))

        logger.info(f"Starting deep research on query: {query}")
        logger.debug(
            f"Parameters: max_depth={max_depth}, results_per_search={results_per_search}, time_limit={time_limit_seconds}s"
        )

        # Initialize research context and set deadline
        context = ResearchContext(query=query, max_depth=max_depth)
        deadline = time.time() + time_limit_seconds

        try:
            # Initialize tools if needed
            if self.search_tool is None:
                self.search_tool = WebSearch()
                logger.debug("Initialized WebSearch tool")

            if self.llm is None:
                self.llm = LLM()
                logger.debug("Initialized LLM")

            # Initiate research process with optimized query
            optimized_query = await self._generate_optimized_query(query)
            logger.info(f"Optimized query: {optimized_query}")

            await self._research_graph(
                context=context,
                query=optimized_query,
                results_count=results_per_search,
                deadline=deadline,
            )

            logger.info(
                f"Research completed: {len(context.insights)} insights found, depth {context.current_depth} reached"
            )

        except ToolError as e:
            logger.error(f"Research error: {str(e)}")
        except EnterpriseAIError as e:
            logger.error(f"Enterprise AI error during research: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during research: {str(e)}")

        # Prepare final summary
        summary = ResearchSummary(
            query=query,
            insights=sorted(context.insights, key=lambda x: x.relevance_score, reverse=True)[
                :max_insights
            ],
            visited_urls=context.visited_urls,
            depth_reached=context.current_depth,
        )

        return summary

    async def _generate_optimized_query(self, query: str) -> str:
        """
        Generate an optimized search query using LLM.

        Args:
            query: Original research query

        Returns:
            Optimized query for better search results
        """
        try:
            logger.debug(f"Optimizing query: {query}")
            prompt = OPTIMIZE_QUERY_PROMPT.format(query=query)

            # Prepare the request for the LLM
            messages = [{"role": "user", "content": prompt}]

            # Get a response from the LLM
            if self.llm is None:
                raise ToolError("LLM is not initialized")
            response = await self.llm.complete(messages=messages)

            # Extract the optimized query from the response
            optimized_query = ""
            if response and hasattr(response, "content"):
                content = response.content
                if isinstance(content, str):
                    optimized_query = content.strip()

            if not optimized_query:
                logger.warning("Generated empty optimized query, using original")
                return query

            logger.info(f"Optimized query: '{optimized_query}'")
            return optimized_query
        except Exception as e:
            logger.warning(f"Failed to optimize query: {str(e)}")
            return query  # Fall back to original query on error

    async def _research_graph(
        self,
        context: ResearchContext,
        query: str,
        results_count: int,
        deadline: float,
    ) -> None:
        """
        Run a complete research cycle (search, analyze, generate follow-ups).

        Args:
            context: Current research context
            query: Query to research
            results_count: Number of results to analyze
            deadline: Timestamp for execution deadline
        """
        # Check termination conditions
        if time.time() >= deadline or context.current_depth >= context.max_depth:
            if time.time() >= deadline:
                logger.info("Research cycle terminated: time limit reached")
            elif context.current_depth >= context.max_depth:
                logger.info(f"Research cycle terminated: max depth {context.max_depth} reached")
            return

        # Log current research step
        logger.info(f"Research cycle at depth {context.current_depth + 1} for query: {query}")

        # 1. Web search
        search_results = await self._search_web(query, results_count)
        if not search_results:
            logger.warning(f"No search results found for query: {query}")
            return

        # 2. Extract insights
        logger.debug(f"Analyzing {len(search_results)} search results")
        new_insights = await self._extract_insights(
            context, search_results, context.query, deadline
        )
        if not new_insights:
            logger.warning("No insights extracted from search results")
            return

        logger.info(f"Extracted {len(new_insights)} insights from search results")

        # 3. Generate follow-up queries
        follow_up_queries = await self._generate_follow_ups(new_insights, query, context.query)
        context.follow_up_queries.extend(follow_up_queries)
        logger.info(f"Generated {len(follow_up_queries)} follow-up queries")

        # Update depth and proceed to next level
        context.current_depth += 1

        # 4. Continue research with follow-up queries
        if follow_up_queries and context.current_depth < context.max_depth:
            logger.debug(f"Processing follow-up queries at depth {context.current_depth}")

            tasks = []  # Create a list to hold the tasks
            for follow_up in follow_up_queries[:2]:  # Limit branching factor
                if time.time() >= deadline:
                    logger.info("Follow-up processing terminated: time limit reached")
                    break

                logger.debug(f"Scheduling follow-up query: {follow_up}")
                # Create a coroutine for the recursive research call
                task = self._research_graph(
                    context=context,
                    query=follow_up,
                    results_count=max(1, results_count - 1),  # Reduce result count
                    deadline=deadline,
                )
                tasks.append(task)  # Add the task to the list

            # Run all the created tasks concurrently
            if tasks:
                logger.debug(f"Running {len(tasks)} follow-up queries in parallel")
                await asyncio.gather(*tasks)

    async def _search_web(self, query: str, results_count: int) -> List[SearchResult]:
        """
        Perform web search for the given query.

        Args:
            query: Search query
            results_count: Number of results to retrieve

        Returns:
            List of search results
        """
        logger.debug(f"Searching web for: {query}")

        if self.search_tool is None:
            self.search_tool = WebSearch()
            logger.debug("Initialized WebSearch tool")

        search_response = await self.search_tool.execute(
            query=query, num_results=results_count, fetch_content=True
        )

        results = getattr(search_response, "results", [])
        logger.debug(f"Retrieved {len(results)} search results")
        return results

    async def _extract_insights(
        self,
        context: ResearchContext,
        results: List[SearchResult],
        original_query: str,
        deadline: float,
    ) -> List[ResearchInsight]:
        """
        Extract insights from search results.

        Args:
            context: Current research context
            results: Search results to analyze
            original_query: Original research query
            deadline: Timestamp for execution deadline

        Returns:
            List of extracted insights
        """
        all_insights = []

        for result_index, rst in enumerate(results):
            # Skip if URL already visited or time exceeded
            if rst.url in context.visited_urls or time.time() >= deadline:
                if rst.url in context.visited_urls:
                    logger.debug(f"Skipping already visited URL: {rst.url}")
                else:
                    logger.debug("Analysis terminated: time limit reached")
                continue

            logger.debug(f"Analyzing result {result_index + 1}/{len(results)}: {rst.url}")
            context.visited_urls.add(rst.url)

            # Skip if no content available
            if not rst.raw_content:
                logger.debug(f"Skipping result with no content: {rst.url}")
                continue

            # Extract insights using LLM
            insights = await self._analyze_content(
                content=rst.raw_content[:10000],  # Limit content size
                url=rst.url,
                title=rst.title,
                query=original_query,
            )

            all_insights.extend(insights)
            context.insights.extend(insights)

            # Log discovered insights
            logger.info(f"Extracted {len(insights)} insights from {rst.url}")

        return all_insights

    async def _generate_follow_ups(
        self, insights: List[ResearchInsight], current_query: str, original_query: str
    ) -> List[str]:
        """
        Generate follow-up queries based on insights.

        Args:
            insights: Recently discovered insights
            current_query: Current research query
            original_query: Original research query

        Returns:
            List of follow-up queries
        """
        if not insights:
            logger.debug("No insights available for follow-up generation")
            return []

        # Format insights for the prompt
        insights_text = "\n".join([f"- {insight.content}" for insight in insights[:5]])

        # Create prompt for generating follow-up queries
        prompt = GENERATE_FOLLOW_UPS_PROMPT.format(
            original_query=original_query,
            current_query=current_query,
            insights=insights_text,
        )

        # Get follow-up queries from LLM
        try:
            logger.debug("Generating follow-up queries")

            if self.llm is None:
                self.llm = LLM()
                logger.debug("Initialized LLM")

            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.complete(messages=messages)
            content = ""
            if hasattr(response, "content") and isinstance(response.content, str):
                content = response.content

            # Extract queries from response
            queries = []
            for line in content.strip().split("\n"):
                # Look for numbered lines, bulleted lines, or similar formatting
                if re.match(r"^\s*(\d+\.|\*|-|\•)\s+", line):
                    query_text = re.sub(r"^\s*(\d+\.|\*|-|\•)\s+", "", line).strip()
                    if query_text and len(query_text) > 10:  # Avoid too short queries
                        queries.append(query_text)

            # Ensure we don't return more than 3 queries
            result = queries[:3]
            logger.info(f"Generated {len(result)} follow-up queries")
            return result
        except Exception as e:
            logger.error(f"Error generating follow-up queries: {str(e)}")
            return []

    async def _analyze_content(
        self, content: str, url: str, title: str, query: str
    ) -> List[ResearchInsight]:
        """
        Extract insights from content based on relevance to query.

        Args:
            content: Content to analyze
            url: Source URL
            title: Source title
            query: Research query

        Returns:
            List of extracted insights
        """
        logger.debug(f"Analyzing content from: {url}")

        prompt = EXTRACT_INSIGHTS_PROMPT.format(
            query=query,
            content=content[:5000],  # Limit content size
        )

        try:
            if self.llm is None:
                self.llm = LLM()
                logger.debug("Initialized LLM")

            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.complete(messages=messages)
            insights = []

            response_content = ""
            if response and hasattr(response, "content") and isinstance(response.content, str):
                response_content = response.content

                # Parse insights from the response text
                current_insight: Dict[str, Any] = {
                    "content": "",
                    "relevance_score": DEFAULT_RELEVANCE_SCORE,
                }
                for line in response_content.strip().split("\n"):
                    # Check for new insight marker
                    if match := INSIGHT_MARKER_PATTERN.match(line):
                        # If we have a previous insight, add it
                        if current_insight["content"]:
                            # Ensure content is a string
                            insight_content = ""
                            if isinstance(current_insight["content"], str):
                                insight_content = current_insight["content"].strip()
                            else:
                                insight_content = str(current_insight["content"])

                            # Ensure relevance_score is a float
                            relevance_score = DEFAULT_RELEVANCE_SCORE
                            if isinstance(current_insight["relevance_score"], (int, float)):
                                relevance_score = float(current_insight["relevance_score"])

                            insights.append(
                                ResearchInsight(
                                    content=insight_content,
                                    source_url=url,
                                    source_title=title,
                                    relevance_score=relevance_score,
                                )
                            )
                            current_insight = {
                                "content": "",
                                "relevance_score": DEFAULT_RELEVANCE_SCORE,
                            }

                        # Start new insight
                        current_insight["content"] = match.group(1)
                    elif "relevance" in line.lower() and (
                        score_match := RELEVANCE_SCORE_PATTERN.search(line)
                    ):
                        # Extract relevance score
                        try:
                            score = float(score_match.group(1))
                            if 0 <= score <= 1:
                                current_insight["relevance_score"] = score
                        except ValueError:
                            pass
                    elif current_insight["content"]:
                        # Continue current insight
                        if isinstance(current_insight["content"], str):
                            current_insight["content"] += " " + line.strip()
                        else:
                            current_insight["content"] = (
                                str(current_insight["content"]) + " " + line.strip()
                            )

                # Add the last insight if any
                if current_insight["content"]:
                    # Ensure content is a string
                    insight_content = ""
                    if isinstance(current_insight["content"], str):
                        insight_content = current_insight["content"].strip()
                    else:
                        insight_content = str(current_insight["content"])

                    # Ensure relevance_score is a float
                    relevance_score = DEFAULT_RELEVANCE_SCORE
                    if isinstance(current_insight["relevance_score"], (int, float)):
                        relevance_score = float(current_insight["relevance_score"])

                    insights.append(
                        ResearchInsight(
                            content=insight_content,
                            source_url=url,
                            source_title=title,
                            relevance_score=relevance_score,
                        )
                    )

            # If no insights found, use fallback approach
            if not insights:
                logger.warning(
                    f"Could not parse insights from LLM response for {url}. Using fallback."
                )
                insights.append(
                    ResearchInsight(
                        content=f"Information found about {title or url}."[:FALLBACK_CONTENT_LIMIT],
                        source_url=url,
                        source_title=title,
                        relevance_score=FALLBACK_RELEVANCE_SCORE,
                    )
                )

            logger.debug(f"Extracted {len(insights)} insights from {url}")
            return insights
        except Exception as e:
            logger.error(f"Error analyzing content from {url}: {str(e)}")
            # Return fallback insight on error
            return [
                ResearchInsight(
                    content=f"Information related to the query was found at {title or url}."[
                        :FALLBACK_CONTENT_LIMIT
                    ],
                    source_url=url,
                    source_title=title,
                    relevance_score=FALLBACK_RELEVANCE_SCORE,
                )
            ]

    async def cleanup(self) -> None:
        """Clean up resources used by the deep research tool."""
        logger.info("Cleaning up deep research resources")

        # Clean up WebSearch tool if initialized
        if self.search_tool is not None:
            try:
                await self.search_tool.cleanup()
                logger.debug("WebSearch tool cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up WebSearch tool: {e}")

            self.search_tool = None
