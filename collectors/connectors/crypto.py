from __future__ import annotations

from typing import Any, Callable


TaskMap = dict[str, Callable[[], Any]]


def build_crypto_tasks(*, config: dict[str, Any]) -> TaskMap:
    from collectors.digital_oracle import (
        CoinGeckoMarketQuery,
        CoinGeckoPriceQuery,
        CoinGeckoProvider,
        DeribitFuturesCurveQuery,
        DeribitOptionChainQuery,
        DeribitProvider,
    )

    provider_config = dict(config.get("providers", {}).get("crypto", {}))
    if provider_config.get("enabled", True) is False:
        return {}

    tasks: TaskMap = {}
    if bool(provider_config.get("coingecko", True)):
        coin_ids = tuple(provider_config.get("coin_ids", ("bitcoin", "ethereum")))
        market_limit = int(provider_config.get("market_limit", 20))
        tasks["crypto.coingecko.prices"] = lambda: CoinGeckoProvider().get_prices(
            CoinGeckoPriceQuery(coin_ids=coin_ids)
        )
        tasks["crypto.coingecko.global"] = lambda: CoinGeckoProvider().get_global()
        tasks["crypto.coingecko.markets"] = lambda: CoinGeckoProvider().list_markets(
            CoinGeckoMarketQuery(per_page=market_limit)
        )

    if bool(provider_config.get("deribit", True)):
        currencies = tuple(provider_config.get("deribit_currencies", ("BTC", "ETH")))
        orderbook_instruments = tuple(provider_config.get("deribit_orderbook_instruments", ()))
        orderbook_depth = int(provider_config.get("deribit_orderbook_depth", 5))
        for currency in currencies:
            tasks[f"crypto.deribit.{currency}.futures_curve"] = (
                lambda c=str(currency): DeribitProvider().get_futures_term_structure(
                    DeribitFuturesCurveQuery(currency=c)
                )
            )
            if bool(provider_config.get("deribit_options", True)):
                tasks[f"crypto.deribit.{currency}.option_chain"] = (
                    lambda c=str(currency): DeribitProvider().get_option_chain(
                        DeribitOptionChainQuery(currency=c)
                    )
                )
        for instrument_name in orderbook_instruments:
            tasks[f"crypto.deribit.orderbook.{safe_task_label(instrument_name)}"] = (
                lambda name=str(instrument_name), depth=orderbook_depth: DeribitProvider().get_order_book(
                    name,
                    depth=depth,
                )
            )
    return tasks


def safe_task_label(value: object) -> str:
    return str(value).replace(" ", "_").replace("/", "_").replace(".", "_")[:80]
