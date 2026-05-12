from __future__ import annotations

from typing import Any, Callable


TaskMap = dict[str, Callable[[], Any]]


def build_prediction_market_tasks(*, task: str, symbols: list[str], config: dict[str, Any]) -> TaskMap:
    from collectors.digital_oracle import (
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
        event_tickers = tuple(provider_config.get("kalshi_event_tickers", ()))
        orderbook_tickers = tuple(provider_config.get("kalshi_orderbook_tickers", ()))
        orderbook_depth = int(provider_config.get("kalshi_orderbook_depth", 10))
        tasks["prediction.kalshi.markets"] = lambda: KalshiProvider().list_markets(
            KalshiMarketQuery(
                limit=limit,
                status=status,
                series_ticker=series_ticker,
                event_ticker=event_ticker,
                tickers=tickers,
            )
        )
        if event_ticker and event_ticker not in event_tickers:
            event_tickers = (event_ticker, *event_tickers)
        for ticker in event_tickers:
            tasks[f"prediction.kalshi.event.{safe_task_label(ticker)}"] = (
                lambda t=str(ticker): KalshiProvider().get_event(t)
            )
        for ticker in orderbook_tickers:
            tasks[f"prediction.kalshi.orderbook.{safe_task_label(ticker)}"] = (
                lambda t=str(ticker), depth=orderbook_depth: KalshiProvider().get_order_book(t, depth=depth)
            )

    if bool(provider_config.get("polymarket", True)):
        limit = int(provider_config.get("polymarket_limit", 10))
        tags = tuple(provider_config.get("polymarket_tag_slugs", ("economy", "crypto", "fed")))
        title_contains = provider_config.get("polymarket_title_contains")
        event_slugs = tuple(provider_config.get("polymarket_event_slugs", ()))
        orderbook_token_ids = tuple(provider_config.get("polymarket_orderbook_token_ids", ()))
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
        for slug in event_slugs:
            tasks[f"prediction.polymarket.event.{safe_task_label(slug)}"] = (
                lambda s=str(slug): PolymarketProvider().get_event(s)
            )
        for token_id in orderbook_token_ids:
            tasks[f"prediction.polymarket.orderbook.{safe_task_label(token_id)}"] = (
                lambda token=str(token_id): PolymarketProvider().get_order_book(token)
            )
    return tasks


def safe_task_label(value: object) -> str:
    return str(value).replace(" ", "_").replace("/", "_").replace(".", "_")[:80]
