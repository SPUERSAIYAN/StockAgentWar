from __future__ import annotations

from typing import Any, Callable


TaskMap = dict[str, Callable[[], Any]]


def build_web_search_tasks(*, task: str, symbols: list[str], config: dict[str, Any]) -> TaskMap:
    from collectors.digital_oracle import WebPageQuery, WebSearchProvider, WebSearchQuery

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
    max_page_chars = int(provider_config.get("max_page_chars", 8000))
    for index, url in enumerate(provider_config.get("pages", ()), 1):
        tasks[f"web.page.{index}.{safe_task_label(url)}"] = (
            lambda page_url=str(url), limit=max_page_chars: WebSearchProvider().fetch_page(
                WebPageQuery(url=page_url, max_chars=limit)
            )
        )
    return tasks


def safe_task_label(value: object) -> str:
    return str(value).replace(" ", "_").replace("/", "_").replace(".", "_")[:80]
