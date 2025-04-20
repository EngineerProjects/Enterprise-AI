"""Google search engine implementation."""

from typing import Any, List

from googlesearch import search

from enterprise_ai.tool.research.search.base import SearchItem, WebSearchEngine


class GoogleSearchEngine(WebSearchEngine):
    """Implementation of Google search engine."""

    def perform_search(
        self, query: str, num_results: int = 10, *args: Any, **kwargs: Any
    ) -> List[SearchItem]:
        """
        Google search engine.

        Args:
            query: The search query
            num_results: Maximum number of results to return
            args: Additional positional arguments
            kwargs: Additional keyword arguments

        Returns:
            List of search results formatted according to SearchItem model
        """
        raw_results = search(query, num_results=num_results, advanced=True)

        results = []
        for i, item in enumerate(raw_results):
            if isinstance(item, str):
                # If it's just a URL
                results.append(SearchItem(title=f"Google Result {i + 1}", url=item, description=""))
            else:
                results.append(
                    SearchItem(title=item.title, url=item.url, description=item.description)
                )

        return results
