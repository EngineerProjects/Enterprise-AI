"""Deep research tool for Enterprise AI."""

import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from enterprise_ai.exceptions import EnterpriseAIError
from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult  # Using unified ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.tool.research.web_search import SearchResult, WebSearch

logger = get_optimized_logger("tool.research.deep_research")

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

Extract up to 3 most important insights from this content. Format your response as:

1. [Insight content here]
   Relevance: [0.0-1.0]

2. [Second insight content here]
   Relevance: [0.0-1.0]

3. [Third insight content here]
   Relevance: [0.0-1.0]
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

Format your response as:
1. [First follow-up query]
2. [Second follow-up query]
3. [Third follow-up query]
"""

# Constants for insight parsing
DEFAULT_RELEVANCE_SCORE = 1.0
FALLBACK_RELEVANCE_SCORE = 0.7
FALLBACK_CONTENT_LIMIT = 500
INSIGHT_MARKER_PATTERN = re.compile(r"^\s*(?:\d+\.|-|\*|•)\s*(.*)")
RELEVANCE_SCORE_PATTERN = re.compile(r"relevance.*?:.*?(\d\.?\d*)", re.IGNORECASE)


def _get_llm_completion(messages, model_name=None, provider_name=None, **kwargs):
    """Lazy import and execute LLM completion with configurable model."""
    try:
        from enterprise_ai.llm import complete, CompletionOptions
        from enterprise_ai.schema import Message  # Updated import
        from enterprise_ai.config import get_config
        
        # Use provided model/provider or fall back to config defaults
        provider = provider_name or get_config("llm.default_provider", "ollama")
        model = model_name or get_config("llm.default_model", "llama3.2")

        timeout = kwargs.get('timeout') or get_config("llm.timeout", 120.0)
        
        # Log what we're using for debugging
        logger.debug("Using LLM provider: %s, model: %s", provider, model)
        
        return complete(
            messages=messages,
            provider_name=provider,
            model_name=model,
            options=CompletionOptions(
                temperature=kwargs.get('temperature', 0.2),
                max_tokens=kwargs.get('max_tokens', 500),
                timeout=timeout
            )
        )
    except ImportError as e:
        logger.error("Failed to import LLM completion: %s", e)
        raise ToolError("LLM completion not available for research analysis")
    except Exception as e:
        logger.error("LLM completion failed: %s", e)
        # Return a fallback response instead of crashing
        class FallbackResponse:
            def __init__(self, content):
                self.content = content
        
        return FallbackResponse('{"analysis": "LLM analysis temporarily unavailable", "relevance": 0.5}')


class ResearchInsight(BaseModel):
    """A single insight discovered during research."""

    model_config = ConfigDict(frozen=True)

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
    """Comprehensive summary of deep research results using unified ToolResult."""

    query: str = Field(description="The original research query")
    insights: List[ResearchInsight] = Field(
        default_factory=list, description="Key insights discovered"
    )
    visited_urls: Set[str] = Field(default_factory=set, description="URLs visited during research")
    depth_reached: int = Field(default=0, description="Maximum depth of research reached", ge=0)

    def __init__(self, **data: Any) -> None:
        # Format the research summary for the unified result field
        query = data.get("query", "")
        insights = data.get("insights", [])
        visited_urls = data.get("visited_urls", set())
        depth_reached = data.get("depth_reached", 0)
        
        formatted_result = self._format_research_summary(query, insights, visited_urls, depth_reached)
        
        # Set unified fields
        data["result"] = formatted_result
        data["tool_call_id"] = data.get("tool_call_id", "")
        data["name"] = data.get("name", "deep_research")
        data["success"] = not bool(data.get("error"))
        
        super().__init__(**data)

    def _format_research_summary(
        self, 
        query: str, 
        insights: List[ResearchInsight], 
        visited_urls: Set[str], 
        depth_reached: int
    ) -> str:
        """Format research summary for display."""
        # Group and sort insights by relevance
        grouped_insights: Dict[str, List[ResearchInsight]] = {
            "Key Findings": [i for i in insights if i.relevance_score >= 0.8],
            "Additional Information": [i for i in insights if 0.5 <= i.relevance_score < 0.8],
            "Supplementary Information": [i for i in insights if i.relevance_score < 0.5],
        }

        sections = [
            f"# Research: {query}\n",
            f"**Sources**: {len(visited_urls)} | **Depth**: {depth_reached + 1}\n",
        ]

        for section_title, section_insights in grouped_insights.items():
            if section_insights:
                sections.append(f"## {section_title}")
                for insight in section_insights:
                    sections.extend([
                        insight.content,
                        f"> Source: [{insight.source_title or 'Link'}]({insight.source_url})\n",
                    ])

        return "\n".join(sections)

    @property
    def output(self) -> str:
        """Backward compatibility property."""
        return self.result


@register_tool(category="research", capabilities=["search", "network_access", "analysis"])
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

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.SEARCH}

    # Tool requires initialization
    requires_initialization: bool = True

    # LLM Configuration fields (ADDED)
    llm_provider: Optional[str] = Field(default=None, description="LLM provider for content analysis")
    llm_model: Optional[str] = Field(default=None, description="LLM model for content analysis")

    # Tool fields
    search_tool: Optional[WebSearch] = Field(default=None, exclude=True)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize DeepResearch tool with configurable LLM.
        
        Args:
            llm_provider: LLM provider to use for analysis (e.g., "ollama", "openai")
            llm_model: Model name to use for analysis (e.g., "llama3.2:3b", "gpt-4")
        """
        model_fields = self.__class__.model_fields

        # Load execution timeout from config for tool config
        from enterprise_ai.config import get_config
        default_timeout = get_config("execution.timeout", 180.0)

        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            config=config or ToolConfig(
                timeout=default_timeout,  # Use config timeout
                max_retries=2,
                cache_results=True,
            ),
            llm_provider=llm_provider,
            llm_model=llm_model,
            **kwargs,
        )

        # Initialize dependent tools
        self.search_tool = None

        logger.debug("DeepResearch tool initialized with timeout: %.1fs", self.config.timeout)

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the research tool and its dependencies."""
        try:
            self.search_tool = WebSearch()
            await self.search_tool.initialize()
            
            logger.info("DeepResearch tool successfully initialized")
            return True
        except Exception as e:
            logger.error("Failed to initialize DeepResearch tool: %s", e)
            return False

    async def execute(self, **kwargs: Any) -> ResearchSummary:
        """Execute deep research on the given query."""
        # Extract parameters with proper type conversion
        query = kwargs.get("query")
        if not query:
            logger.error("Missing required 'query' parameter")
            return ResearchSummary(
                query="",
                insights=[],
                visited_urls=set(),
                depth_reached=0,
                error="Query parameter is required",
                tool_call_id="",
                name=self.name
            )

        # FIX: Convert string parameters to integers safely
        try:
            max_depth = max(1, min(int(kwargs.get("max_depth", 2)), 5))
            results_per_search = max(1, min(int(kwargs.get("results_per_search", 5)), 20))
            max_insights = int(kwargs.get("max_insights", 20))
            config_timeout = getattr(self.config, "timeout", 120)
            time_limit_seconds = int(kwargs.get("time_limit_seconds", config_timeout))
        except (ValueError, TypeError) as e:
            logger.error("Invalid parameter types: %s", e)
            return ResearchSummary(
                query=query,
                insights=[],
                visited_urls=set(),
                depth_reached=0,
                error=f"Invalid parameter types: {e}",
                tool_call_id="",
                name=self.name
            )

        logger.info("Starting deep research on query: %s", query)
        logger.debug("Parameters: max_depth=%s, results_per_search=%s", max_depth, results_per_search)

        # Initialize research context
        context = ResearchContext(query=query, max_depth=max_depth)
        deadline = time.time() + time_limit_seconds

        try:
            # Initialize tools if needed
            if self.search_tool is None:
                self.search_tool = WebSearch()
                await self.search_tool.initialize()

            # Start research process
            optimized_query = await self._generate_optimized_query(query)
            logger.info("Optimized query: %s", optimized_query)

            await self._research_graph(
                context=context,
                query=optimized_query,
                results_count=results_per_search,
                deadline=deadline,
            )

            logger.info("Research completed: %s insights, depth %s", len(context.insights), context.current_depth)

        except ToolError as e:
            logger.error("Research error: %s", str(e))
        except EnterpriseAIError as e:
            logger.error("Enterprise AI error during research: %s", str(e))
        except Exception as e:
            logger.error("Unexpected error during research: %s", str(e))

        # Prepare final summary
        summary = ResearchSummary(
            query=query,
            insights=sorted(context.insights, key=lambda x: x.relevance_score, reverse=True)[:max_insights],
            visited_urls=context.visited_urls,
            depth_reached=context.current_depth,
            tool_call_id="",
            name=self.name
        )

        return summary

    async def _generate_optimized_query(self, query: str) -> str:
        """Generate an optimized search query using the configured LLM."""
        try:
            logger.debug("Optimizing query: %s", query)
            prompt = OPTIMIZE_QUERY_PROMPT.format(query=query)

            # Use lazy import pattern with our helper function
            from enterprise_ai.schema import Message
            messages = [Message.user_message(prompt)]

            response = _get_llm_completion(
                messages=messages,
                model_name=self.llm_model,
                provider_name=self.llm_provider,
                temperature=0.1,
                max_tokens=100
            )

            if hasattr(response, 'content') and response.content:
                optimized_query = response.content.strip()
                if optimized_query:
                    logger.info("Optimized query: '%s'", optimized_query)
                    return optimized_query

            logger.warning("Generated empty optimized query, using original")
            return query
        except Exception as e:
            logger.warning("Failed to optimize query: %s", str(e))
            return query

    async def _research_graph(
        self,
        context: ResearchContext,
        query: str,
        results_count: int,
        deadline: float,
    ) -> None:
        """Run a complete research cycle."""
        # Check termination conditions
        if time.time() >= deadline or context.current_depth >= context.max_depth:
            if time.time() >= deadline:
                logger.info("Research cycle terminated: time limit reached")
            elif context.current_depth >= context.max_depth:
                logger.info("Research cycle terminated: max depth %s reached", context.max_depth)
            return

        logger.info("Research cycle at depth %s for query: %s", context.current_depth + 1, query)

        # 1. Web search
        search_results = await self._search_web(query, results_count)
        if not search_results:
            logger.warning("No search results found for query: %s", query)
            return

        # 2. Extract insights
        logger.debug("Analyzing %s search results", len(search_results))
        new_insights = await self._extract_insights(context, search_results, context.query, deadline)
        if not new_insights:
            logger.warning("No insights extracted from search results")
            return

        logger.info("Extracted %s insights from search results", len(new_insights))

        # 3. Generate follow-up queries
        follow_up_queries = await self._generate_follow_ups(new_insights, query, context.query)
        context.follow_up_queries.extend(follow_up_queries)
        logger.info("Generated %s follow-up queries", len(follow_up_queries))

        # Update depth
        context.current_depth += 1

        # 4. Continue research with follow-up queries
        if follow_up_queries and context.current_depth < context.max_depth:
            logger.debug("Processing follow-up queries at depth %s", context.current_depth)

            tasks = []
            for follow_up in follow_up_queries[:2]:  # Limit branching factor
                if time.time() >= deadline:
                    logger.info("Follow-up processing terminated: time limit reached")
                    break

                logger.debug("Scheduling follow-up query: %s", follow_up)
                task = self._research_graph(
                    context=context,
                    query=follow_up,
                    results_count=max(1, results_count - 1),
                    deadline=deadline,
                )
                tasks.append(task)

            if tasks:
                logger.debug("Running %s follow-up queries in parallel", len(tasks))
                await asyncio.gather(*tasks)

    async def _search_web(self, query: str, results_count: int) -> List[SearchResult]:
        """Perform web search for the given query."""
        logger.debug("Searching web for: %s", query)

        if self.search_tool is None:
            self.search_tool = WebSearch()
            await self.search_tool.initialize()

        search_response = await self.search_tool.execute(
            query=query, num_results=results_count, fetch_content=True
        )

        results = getattr(search_response, "results", [])
        logger.debug("Retrieved %s search results", len(results))
        return results

    async def _extract_insights(
        self,
        context: ResearchContext,
        results: List[SearchResult],
        original_query: str,
        deadline: float,
    ) -> List[ResearchInsight]:
        """Extract insights from search results."""
        all_insights = []

        for result_index, result in enumerate(results):
            if result.url in context.visited_urls or time.time() >= deadline:
                if result.url in context.visited_urls:
                    logger.debug("Skipping already visited URL: %s", result.url)
                else:
                    logger.debug("Analysis terminated: time limit reached")
                continue

            logger.debug("Analyzing result %s/%s: %s", result_index + 1, len(results), result.url)
            context.visited_urls.add(result.url)

            if not result.raw_content:
                logger.debug("Skipping result with no content: %s", result.url)
                continue

            insights = await self._analyze_content(
                content=result.raw_content[:10000],
                url=result.url,
                title=result.title,
                query=original_query,
            )

            all_insights.extend(insights)
            context.insights.extend(insights)
            logger.info("Extracted %s insights from %s", len(insights), result.url)

        return all_insights

    async def _generate_follow_ups(
        self, insights: List[ResearchInsight], current_query: str, original_query: str
    ) -> List[str]:
        """Generate follow-up queries based on insights."""
        if not insights:
            logger.debug("No insights available for follow-up generation")
            return []

        insights_text = "\n".join([f"- {insight.content}" for insight in insights[:5]])
        prompt = GENERATE_FOLLOW_UPS_PROMPT.format(
            original_query=original_query,
            current_query=current_query,
            insights=insights_text,
        )

        try:
            logger.debug("Generating follow-up queries")

            from enterprise_ai.schema import Message
            messages = [Message.user_message(prompt)]
            
            response = _get_llm_completion(
                messages=messages,
                model_name=self.llm_model,
                provider_name=self.llm_provider,
                temperature=0.3,
                max_tokens=200
            )

            if not (hasattr(response, 'content') and response.content):
                return []

            content = response.content.strip()
            queries = []
            
            for line in content.split("\n"):
                if re.match(r"^\s*(\d+\.|\*|-|\•)\s+", line):
                    query_text = re.sub(r"^\s*(\d+\.|\*|-|\•)\s+", "", line).strip()
                    if query_text and len(query_text) > 10:
                        queries.append(query_text)

            result = queries[:3]
            logger.info("Generated %s follow-up queries", len(result))
            return result
        except Exception as e:
            logger.error("Error generating follow-up queries: %s", str(e))
            return []

    async def _analyze_content(
        self, content: str, url: str, title: str, query: str
    ) -> List[ResearchInsight]:
        """Extract insights from content based on relevance to query."""
        logger.debug("Analyzing content from: %s", url)

        prompt = EXTRACT_INSIGHTS_PROMPT.format(
            query=query,
            content=content[:5000],
        )

        try:
            from enterprise_ai.schema import Message
            messages = [Message.user_message(prompt)]
            
            response = _get_llm_completion(
                messages=messages,
                model_name=self.llm_model,
                provider_name=self.llm_provider,
                temperature=0.2,
                max_tokens=500
            )

            insights = []
            
            if not (hasattr(response, 'content') and response.content):
                logger.warning("No response content for %s", url)
                return [self._create_fallback_insight(url, title)]

            response_content = response.content.strip()
            current_insight: Dict[str, Any] = {
                "content": "",
                "relevance_score": DEFAULT_RELEVANCE_SCORE,
            }
            
            for line in response_content.split("\n"):
                # Check for new insight marker
                if match := INSIGHT_MARKER_PATTERN.match(line):
                    # Save previous insight if exists
                    if current_insight["content"]:
                        insights.append(self._create_insight_from_dict(current_insight, url, title))
                        current_insight = {
                            "content": "",
                            "relevance_score": DEFAULT_RELEVANCE_SCORE,
                        }

                    # Start new insight
                    current_insight["content"] = match.group(1)
                elif "relevance" in line.lower() and (score_match := RELEVANCE_SCORE_PATTERN.search(line)):
                    # Extract relevance score
                    try:
                        score = float(score_match.group(1))
                        if 0 <= score <= 1:
                            current_insight["relevance_score"] = score
                    except ValueError:
                        pass
                elif current_insight["content"]:
                    # Continue current insight
                    current_insight["content"] += " " + line.strip()

            # Add final insight
            if current_insight["content"]:
                insights.append(self._create_insight_from_dict(current_insight, url, title))

            # Use fallback if no insights found
            if not insights:
                logger.warning("Could not parse insights from LLM response for %s. Using fallback.", url)
                insights.append(self._create_fallback_insight(url, title))

            logger.debug("Extracted %s insights from %s", len(insights), url)
            return insights
        except Exception as e:
            logger.error("Error analyzing content from %s: %s", url, str(e))
            return [self._create_fallback_insight(url, title)]

    def _create_insight_from_dict(self, insight_dict: Dict[str, Any], url: str, title: str) -> ResearchInsight:
        """Create ResearchInsight from dictionary."""
        content = str(insight_dict["content"]).strip()
        relevance = float(insight_dict["relevance_score"])
        
        return ResearchInsight(
            content=content,
            source_url=url,
            source_title=title,
            relevance_score=relevance,
        )

    def _create_fallback_insight(self, url: str, title: str) -> ResearchInsight:
        """Create a fallback insight when parsing fails."""
        return ResearchInsight(
            content=f"Information related to the query was found at {title or url}."[:FALLBACK_CONTENT_LIMIT],
            source_url=url,
            source_title=title,
            relevance_score=FALLBACK_RELEVANCE_SCORE,
        )

    async def cleanup(self) -> None:
        """Clean up resources used by the deep research tool."""
        logger.info("Cleaning up deep research resources")

        if self.search_tool is not None:
            try:
                await self.search_tool.cleanup()
                logger.debug("WebSearch tool cleaned up")
            except Exception as e:
                logger.warning("Error cleaning up WebSearch tool: %s", e)

            self.search_tool = None