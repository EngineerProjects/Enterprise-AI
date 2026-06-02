from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool

MAX_RESULTS = 10


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query.")
    max_results: int = Field(default=5, ge=1, le=MAX_RESULTS, description="Number of results to return.")
    backend: Optional[str] = Field(default=None, description="Search backend: ddgs, exa, tavily. Defaults to ddgs.")


class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Search the web for information. Returns a list of results with titles, URLs, and snippets. "
        "Use for finding documentation, current events, or any information not in the agent's context."
    )
    input_schema = WebSearchInput

    async def call(self, input: WebSearchInput, ctx: ToolContext) -> ToolResult:
        backend = (input.backend or ctx.metadata.get("search_backend", "ddgs")).lower()
        try:
            if backend == "ddgs":
                return await self._ddgs(input.query, input.max_results)
            elif backend == "exa":
                return await self._exa(input.query, input.max_results)
            elif backend == "tavily":
                return await self._tavily(input.query, input.max_results)
            else:
                return ToolResult.error(tool_call_id="", name=self.name, error=f"Unknown backend: {backend!r}")
        except ImportError as e:
            return ToolResult.error(tool_call_id="", name=self.name, error=str(e))

    async def _ddgs(self, query: str, max_results: int) -> ToolResult:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            raise ImportError("duckduckgo-search required: pip install 'enterprise-ai[ddgs]'")
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")
        return ToolResult.ok(tool_call_id="", name=self.name, content="\n---\n".join(results) or "No results found.")

    async def _exa(self, query: str, max_results: int) -> ToolResult:
        try:
            from exa_py import Exa
        except ImportError:
            raise ImportError("exa-py required: pip install 'enterprise-ai[exa]'")
        import os
        exa = Exa(api_key=os.environ.get("EXA_API_KEY", ""))
        resp = exa.search(query, num_results=max_results, use_autoprompt=True)
        results = [f"**{r.title}**\n{r.url}\n{r.highlights or ''}" for r in resp.results]
        return ToolResult.ok(tool_call_id="", name=self.name, content="\n---\n".join(results) or "No results found.")

    async def _tavily(self, query: str, max_results: int) -> ToolResult:
        try:
            from tavily import TavilyClient
        except ImportError:
            raise ImportError("tavily-python required: pip install 'enterprise-ai[tavily]'")
        import os
        client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
        resp = client.search(query, max_results=max_results)
        results = [f"**{r['title']}**\n{r['url']}\n{r.get('content', '')}" for r in resp.get("results", [])]
        return ToolResult.ok(tool_call_id="", name=self.name, content="\n---\n".join(results) or "No results found.")
