from __future__ import annotations

from typing import Any, Callable


TaskMap = dict[str, Callable[[], Any]]


def build_prediction_market_tasks(*, task: str, symbols: list[str], config: dict[str, Any]) -> TaskMap:
    from digital_oracle import (
        KalshiMarketQuery,
        KalshiProvider,
        PolymarketEventQuery,
        PolymarketProvider,
    )

    provider_config = dict(config.get("providers", {}).get("prediction_markets", {}))
    if provider_config.get("enabled", True) is False:
        return {}

    tasks: TaskMap = {}
    if bool(provider_config.get("kalshi", True)):
        limit = int(provider_config.get("kalshi_limit", 10))
        status = provider_config.get("kalshi_status", "open")
        series_ticker = provider_config.get("kalshi_series_ticker")
        event_ticker = provider_config.get("kalshi_event_ticker")
        tickers = tuple(provider_config.get("kalshi_tickers", ()))
        tasks["prediction.kalshi.markets"] = lambda: KalshiProvider().list_markets(
            KalshiMarketQuery(
                limit=limit,
                status=status,
                series_ticker=series_ticker,
                event_ticker=event_ticker,
                tickers=tickers,
            )
        )

    if bool(provider_config.get("polymarket", True)):
        limit = int(provider_config.get("polymarket_limit", 10))
        tags = tuple(provider_config.get("polymarket_tag_slugs", ("economy", "crypto", "fed")))
        title_contains = provider_config.get("polymarket_title_contains")
        for tag in tags:
            tasks[f"prediction.polymarket.{tag}"] = (
                lambda t=tag: PolymarketProvider().list_events(
                    PolymarketEventQuery(limit=limit, slug_contains=str(t), tag_slug=str(t))
                )
            )
        if title_contains:
            tasks["prediction.polymarket.title_search"] = (
                lambda q=str(title_contains): PolymarketProvider().list_events(
                    PolymarketEventQuery(limit=limit, title_contains=q)
                )
            )
    return tasks

