from __future__ import annotations

from typing import Any, Callable


TaskMap = dict[str, Callable[[], Any]]


def build_web_search_tasks(*, task: str, symbols: list[str], config: dict[str, Any]) -> TaskMap:
    from digital_oracle import WebSearchProvider, WebSearchQuery

    provider_config = dict(config.get("providers", {}).get("web_search", {}))
    if provider_config.get("enabled", False) is False:
        return {}

    max_results = int(provider_config.get("max_results", 5))
    configured_queries = list(provider_config.get("queries", ()))
    if not configured_queries:
        symbol_text = " ".join(symbols)
        configured_queries = [
            f"{task} {symbol_text} market news",
            f"{symbol_text} earnings guidance analyst outlook",
        ]

    tasks: TaskMap = {}
    for index, query in enumerate(configured_queries, 1):
        tasks[f"web.search.{index}"] = (
            lambda q=str(query): WebSearchProvider().search(
                WebSearchQuery(query=q, max_results=max_results)
            )
        )
    return tasks

