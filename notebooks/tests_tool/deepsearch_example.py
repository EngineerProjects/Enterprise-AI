#!/usr/bin/env python
"""
Enterprise AI DeepResearch Examples (Mock Implementation)

This script demonstrates the DeepResearch tool concepts:
- Basic deep research capabilities
- Multi-level research with follow-up queries
- Controlling research depth and scope
- Working with structured research summaries
- Analyzing insights and sources
"""

import asyncio
import sys
import time
import random
from typing import Dict, List, Optional, Any, Set

# Import common utilities
from notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    separator,
    AsyncTimer,
    run_async
)

# Set up project path
project_root = setup_project_path()

# Import enterprise_ai modules
from enterprise_ai.tool.core.result import ToolResult
from pydantic import BaseModel, Field


class MockInsight(BaseModel):
    """Simple mock research insight."""
    content: str
    source_url: str
    source_title: Optional[str] = None
    relevance_score: float = 1.0

    def __init__(self, content, source_url, source_title=None, relevance_score=1.0):
        super().__init__(
            content=content,
            source_url=source_url,
            source_title=source_title or "Article on " + source_url.split("//")[1].split("/")[0],
            relevance_score=relevance_score
        )


class MockResearchSummary(ToolResult):
    """Research summary that properly extends ToolResult."""
    query: str = Field(description="The original research query")
    insights: List[MockInsight] = Field(default_factory=list, description="Key insights discovered")
    visited_urls: Set[str] = Field(default_factory=set, description="URLs visited during research")
    depth_reached: int = Field(default=0, description="Maximum depth of research reached", ge=0)


class MockDeepResearch:
    """Mock implementation of the DeepResearch tool."""

    def __init__(self):
        """Initialize the mock deep research tool."""
        # Simulated sources for our mock implementation
        self._domains = [
            "research.org", "academic.edu", "sciencedaily.com",
            "journal.science", "knowledge-base.net", "insights.io",
            "scholar-source.edu", "tech-review.com", "data-analysis.org"
        ]

    async def execute(self, **kwargs):
        """Simulate execution of deep research."""
        # Extract parameters
        query = kwargs.get("query")
        max_depth = min(kwargs.get("max_depth", 2), 3)  # Cap at 3 for example
        results_per_search = min(kwargs.get("results_per_search", 5), 5)  # Cap at 5
        max_insights = min(kwargs.get("max_insights", 20), 20)  # Cap at 20
        time_limit_seconds = kwargs.get("time_limit_seconds", 120)

        # Validate input
        if not query:
            return ToolResult(error="Query parameter is required")

        # Track research process
        visited_urls = set()
        insights = []
        depth_reached = 0

        # Start research process
        deadline = time.time() + time_limit_seconds

        # Simulate optimizing the query
        optimized_query = self._optimize_query(query)
        print_info(f"Optimized query: '{optimized_query}'")

        # Perform initial research (depth 0)
        await self._research_level(
            optimized_query,
            insights,
            visited_urls,
            results_per_search,
            deadline
        )
        depth_reached = 0

        # Perform follow-up research if allowed by depth and time
        follow_up_queries = self._generate_follow_ups(insights, query)

        for depth in range(1, max_depth):
            if time.time() >= deadline or not follow_up_queries:
                break

            print_info(f"Researching at depth {depth+1}...")

            # Take only a few follow-up queries at each level
            for follow_up in follow_up_queries[:2]:
                if time.time() >= deadline:
                    break

                await self._research_level(
                    follow_up,
                    insights,
                    visited_urls,
                    max(1, results_per_search - depth),  # Reduce results as we go deeper
                    deadline
                )

            depth_reached = depth

            # Generate new follow-ups based on accumulated insights
            follow_up_queries = self._generate_follow_ups(insights, query)

        # Limit insights by relevance and max_insights
        sorted_insights = sorted(insights, key=lambda x: x.relevance_score, reverse=True)
        selected_insights = sorted_insights[:max_insights]

        # Generate output summary
        output = self._format_research_summary(query, selected_insights, visited_urls, depth_reached)

        # Create a proper MockResearchSummary instead of ToolResult with added attributes
        result = MockResearchSummary(
            output=output,
            query=query,
            insights=selected_insights,
            visited_urls=visited_urls,
            depth_reached=depth_reached
        )

        return result

    def _optimize_query(self, query):
        """Simulate query optimization."""
        # In a real implementation, this would use LLM to improve the query
        optimized = query

        # Add specificity to make it more "optimized"
        if "comparison" not in query.lower() and random.random() > 0.7:
            optimized += " comparison"
        elif "benefits" not in query.lower() and random.random() > 0.7:
            optimized += " benefits"
        elif "examples" not in query.lower() and random.random() > 0.7:
            optimized += " examples"

        return optimized

    async def _research_level(self, query, insights, visited_urls, results_count, deadline):
        """Simulate research at one level."""
        # Simulate web search
        await asyncio.sleep(0.5)  # Simulate search delay

        # Generate mock search results
        for i in range(results_count):
            if time.time() >= deadline:
                break

            # Create a mock URL
            domain = random.choice(self._domains)
            path = query.lower().replace(" ", "-")
            url = f"https://{domain}/article/{path}-{i+1}"

            # Skip if already visited
            if url in visited_urls:
                continue

            visited_urls.add(url)

            # Simulate content analysis
            await asyncio.sleep(0.3)  # Simulate analysis delay

            # Generate 1-3 insights from this "source"
            insight_count = random.randint(1, 3)
            for j in range(insight_count):
                if time.time() >= deadline:
                    break

                # Generate insight with random relevance
                relevance = round(random.uniform(0.4, 1.0), 1)
                insight = self._generate_insight(query, url, j, relevance)
                insights.append(insight)

                # Simulate insight extraction delay
                await asyncio.sleep(0.1)

    def _generate_insight(self, query, url, index, relevance):
        """Generate a mock insight."""
        topics = {
            "quantum computing": [
                "Quantum computers can solve certain problems exponentially faster than classical computers due to quantum superposition and entanglement.",
                "Quantum error correction is one of the biggest challenges in building large-scale quantum computers.",
                "IBM, Google, and D-Wave are leading companies in quantum computing hardware development.",
                "Quantum supremacy was first claimed by Google in 2019 when their Sycamore processor completed a task in 200 seconds that would take a classical supercomputer 10,000 years."
            ],
            "machine learning": [
                "Deep learning is a subset of machine learning based on artificial neural networks with multiple layers.",
                "Transfer learning allows models trained on one task to be adapted for a different but related task.",
                "TensorFlow and PyTorch are the most widely used frameworks for developing machine learning models.",
                "Reinforcement learning uses a reward-based system to teach agents optimal behaviors through trial and error."
            ],
            "climate change": [
                "Global temperatures have increased by approximately 1°C since pre-industrial times.",
                "Renewable energy sources like solar and wind are key to reducing carbon emissions.",
                "The Paris Agreement aims to limit global warming to well below 2°C above pre-industrial levels.",
                "Climate change is causing more frequent and severe weather events including hurricanes, floods, and wildfires."
            ],
            "gene editing": [
                "CRISPR-Cas9 is a revolutionary gene editing technology that allows precise modification of DNA sequences.",
                "Gene editing raises significant ethical questions about human enhancement and designer babies.",
                "Gene therapy using editing techniques has shown promise for treating genetic diseases like sickle cell anemia.",
                "Regulatory frameworks for gene editing technologies vary significantly across different countries."
            ]
        }

        # Find the closest topic
        best_topic = max(topics.keys(), key=lambda k: sum(1 for word in k.split() if word in query))

        # If no good match, use a generic insight
        if not any(word in query for word in best_topic.split()):
            content = f"Research on {query} shows promising developments in recent years."
        else:
            # Pick an insight from the matched topic
            options = topics[best_topic]
            content = options[index % len(options)]

        # Create the insight
        site_name = url.split("//")[1].split("/")[0]
        return MockInsight(
            content=content,
            source_url=url,
            source_title=f"Article on {query} - {site_name}",
            relevance_score=relevance
        )

    def _generate_follow_ups(self, insights, original_query):
        """Generate follow-up queries based on insights."""
        if not insights:
            return []

        # Extract key terms from insights
        terms = set()
        for insight in insights:
            words = insight.content.split()
            for word in words:
                if len(word) > 5 and word.isalpha():
                    terms.add(word.lower())

        # Generate potential follow-ups
        follow_ups = []

        # Add "advantages" query
        if "advantages" not in original_query.lower() and "benefits" not in original_query.lower():
            follow_ups.append(f"{original_query} advantages and benefits")

        # Add "limitations" query
        if "limitations" not in original_query.lower() and "challenges" not in original_query.lower():
            follow_ups.append(f"{original_query} limitations and challenges")

        # Add specific term queries
        for term in list(terms)[:3]:  # Use up to 3 terms
            if term not in original_query.lower() and len(term) > 5:
                follow_ups.append(f"{original_query} {term}")

        return follow_ups

    def _format_research_summary(self, query, insights, visited_urls, depth_reached):
        """Format research summary as markdown."""
        # Group insights by relevance
        key_findings = [i for i in insights if i.relevance_score >= 0.8]
        additional_info = [i for i in insights if 0.5 <= i.relevance_score < 0.8]
        supplementary = [i for i in insights if i.relevance_score < 0.5]

        sections = [
            f"# Research: {query}\n",
            f"**Sources**: {len(visited_urls)} | **Depth**: {depth_reached + 1}\n",
        ]

        # Add key findings
        if key_findings:
            sections.append("## Key Findings")
            for insight in key_findings:
                sections.extend([
                    insight.content,
                    f"> Source: [{insight.source_title}]({insight.source_url})\n"
                ])

        # Add additional information
        if additional_info:
            sections.append("## Additional Information")
            for insight in additional_info:
                sections.extend([
                    insight.content,
                    f"> Source: [{insight.source_title}]({insight.source_url})\n"
                ])

        # Add supplementary information
        if supplementary:
            sections.append("## Supplementary Information")
            for insight in supplementary:
                sections.extend([
                    insight.content,
                    f"> Source: [{insight.source_title}]({insight.source_url})\n"
                ])

        return "\n".join(sections)


async def basic_research_example() -> None:
    """Example of basic deep research functionality."""
    print_section("Basic Deep Research")

    # Create the mock DeepResearch tool
    research_tool = MockDeepResearch()

    try:
        # Perform basic research on a topic
        print_info("Researching 'quantum computing applications'...")
        print_info("This may take a minute as it performs multiple searches and analyzes content...")

        async with AsyncTimer("Basic research"):
            result = await research_tool.execute(
                query="quantum computing applications",
                max_depth=1,  # Limit depth for example purposes
                results_per_search=3,  # Limit results for example
                max_insights=10  # Limit insights for example
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Error: {result.error}")
            else:
                # Print structured output
                print(result.output)

                # Print summary info
                if hasattr(result, "depth_reached"):
                    print_info(f"\nResearch depth reached: {result.depth_reached + 1}")
                if hasattr(result, "visited_urls"):
                    print_info(f"Sources consulted: {len(result.visited_urls)}")
                if hasattr(result, "insights") and len(result.insights) > 0:
                    print_info(f"Key insights discovered: {len(result.insights)}")

    except Exception as e:
        print_error(f"Error in basic research example: {e}")


async def research_depth_example() -> None:
    """Example of controlling research depth."""
    print_section("Controlling Research Depth")

    # Create the mock DeepResearch tool
    research_tool = MockDeepResearch()

    try:
        # Demonstrate research with different depth settings
        print_info("The DeepResearch tool can explore topics at different depths:")
        print("- Depth 1: Initial research only")
        print("- Depth 2: Initial + one level of follow-up queries")
        print("- Depth 3+: Multiple levels of follow-up exploration")

        # For demonstration, we'll use a shallow depth with a focused topic
        print_info("\nPerforming focused research with depth=1...")

        async with AsyncTimer("Depth-controlled research"):
            result = await research_tool.execute(
                query="CRISPR gene editing ethics",
                max_depth=1,
                results_per_search=2,
                max_insights=5,
                time_limit_seconds=60  # Set a reasonable timeout
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Error: {result.error}")
            else:
                # Print a summary of the research
                if hasattr(result, "query") and hasattr(result, "insights"):
                    print_info(f"Research on: {result.query}")
                    print_info(f"Found {len(result.insights)} insights")

                    # Show the first few insights with sources
                    print("\nSample insights:")
                    for i, insight in enumerate(result.insights[:3], 1):
                        source = insight.source_title or insight.source_url
                        relevance = f"(relevance: {insight.relevance_score:.1f})"
                        print(f"{i}. {insight.content} {relevance}")
                        print(f"   Source: {source}")

                    # Explain the research process
                    print("\nResearch process:")
                    print("1. Query optimization: The original query is refined for better results")
                    print("2. Web search: Multiple sources are searched for relevant information")
                    print("3. Content analysis: Key insights are extracted from each source")
                    print("4. Follow-up (at higher depths): New queries explore gaps in knowledge")
                    print("5. Summary: Findings are organized by relevance and significance")

    except Exception as e:
        print_error(f"Error in research depth example: {e}")


async def research_customization_example() -> None:
    """Example of customizing research parameters."""
    print_section("Research Customization")

    # Create the mock DeepResearch tool
    research_tool = MockDeepResearch()

    try:
        print_info("The DeepResearch tool offers several customization options:")
        print("- max_depth: Controls how many levels of research to perform")
        print("- results_per_search: Number of search results to analyze per query")
        print("- max_insights: Maximum number of insights to return")
        print("- time_limit_seconds: Time cap for the research process")

        print_info("\nPerforming time-limited research (15 seconds)...")

        async with AsyncTimer("Time-limited research"):
            result = await research_tool.execute(
                query="renewable energy trends",
                max_depth=2,
                results_per_search=3,
                max_insights=8,
                time_limit_seconds=15  # Short timeout for example
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Error: {result.error}")
            else:
                print_info("Research completed within time limit")

                # Show how many sources were consulted in the limited time
                if hasattr(result, "visited_urls"):
                    print_info(f"Sources consulted: {len(result.visited_urls)}")
                    print("Sample sources:")
                    for url in list(result.visited_urls)[:3]:
                        print(f"- {url}")

                print_info("\nNote about customization:")
                print("When using DeepResearch in production:")
                print("- For quick overviews: Use depth=1, time_limit=60")
                print("- For thorough research: Use depth=2-3, time_limit=300+")
                print("- For comprehensive analysis: Increase max_insights to 20+")

    except Exception as e:
        print_error(f"Error in research customization example: {e}")


async def research_summary_example() -> None:
    """Example of working with research summaries."""
    print_section("Research Summaries")

    # Create the mock DeepResearch tool
    research_tool = MockDeepResearch()

    try:
        print_info("DeepResearch returns structured research summaries...")
        print_info("Researching 'machine learning frameworks'...")

        async with AsyncTimer("Research summary generation"):
            result = await research_tool.execute(
                query="machine learning frameworks comparison",
                max_depth=1,
                results_per_search=2,
                max_insights=6,
                time_limit_seconds=20
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Error: {result.error}")
            else:
                # Display the structured summary
                print(result.output)

                print_info("\nResearch summaries are structured by relevance:")
                print("- Key Findings: High-relevance insights (score ≥ 0.8)")
                print("- Additional Information: Medium-relevance insights (0.5-0.8)")
                print("- Supplementary Information: Lower-relevance insights (<0.5)")

                print_info("\nEach insight includes:")
                print("- Content: The actual information extracted")
                print("- Source: Where the information was found")
                print("- Relevance: How relevant it is to the original query")

    except Exception as e:
        print_error(f"Error in research summary example: {e}")


async def error_handling_example() -> None:
    """Example of error handling in deep research."""
    print_section("Error Handling")

    # Create the mock DeepResearch tool
    research_tool = MockDeepResearch()

    try:
        # Empty query
        print_info("Attempting research with empty query...")

        async with AsyncTimer("Empty query"):
            result = await research_tool.execute(
                query="",
                max_depth=1
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_warning(f"Expected error: {result.error}")
            else:
                print_error("Command unexpectedly succeeded")
                print(result.output)

        print_info("\nDeepResearch handles various error conditions:")
        print("- Empty or invalid queries")
        print("- Search failures (with graceful fallbacks)")
        print("- Content analysis issues")
        print("- Timeouts (returning partial results)")
        print("- Resource limitations")

        print_info("\nWhen errors occur, the tool will:")
        print("1. Return as many insights as were discovered")
        print("2. Provide clear error information")
        print("3. Include source data for verification")

    except Exception as e:
        print_error(f"Error in error handling example: {e}")


async def run_examples() -> None:
    """Run all deep research examples."""
    try:
        await basic_research_example()
        separator()

        await research_depth_example()
        separator()

        await research_customization_example()
        separator()

        await research_summary_example()
        separator()

        await error_handling_example()

    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point for deep research examples."""
    print_title("Enterprise AI Deep Research Examples (Mock Implementation)")
    print_info("Note: This script demonstrates DeepResearch concepts using a mock implementation")
    print_info("The actual DeepResearch tool performs real web research with LLM-powered analysis")

    try:
        # Run all examples asynchronously
        run_async(run_examples())

        print_success("All deep research examples completed!")
    except Exception as e:
        print_error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
