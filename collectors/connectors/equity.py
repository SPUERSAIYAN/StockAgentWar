from __future__ import annotations

import os
from typing import Any, Callable


TaskMap = dict[str, Callable[[], Any]]


def build_equity_tasks(
    *,
    symbols: list[str],
    config: dict[str, Any],
    is_plain_us_equity: Callable[[str], bool],
    to_yahoo_symbol: Callable[[str], str],
) -> TaskMap:
    from collectors.digital_oracle import (
        EdgarInsiderQuery,
        EdgarProvider,
        EdgarSearchQuery,
        OptionsChainQuery,
        PriceHistoryQuery,
        StooqProvider,
        YahooPriceProvider,
        YFinanceProvider,
    )

    provider_config = dict(config.get("providers", {}).get("us_equity", {}))
    if provider_config.get("enabled", True) is False:
        return {}

    tasks: TaskMap = {}
    price_limit = int(config.get("price_history_limit", 90))
    include_price = bool(provider_config.get("price", True))
    include_weekly = bool(provider_config.get("weekly_price", True))
    include_options = bool(provider_config.get("options", config.get("include_options", True)))
    include_edgar = bool(provider_config.get("edgar", config.get("include_edgar", True)))
    include_edgar_filings = bool(provider_config.get("edgar_filings", include_edgar))
    include_stooq = bool(provider_config.get("stooq_compat", False))
    edgar_user_email = (
        provider_config.get("edgar_user_email")
        or config.get("edgar_user_email")
        or os.getenv("EDGAR_USER_EMAIL")
        or "market-information-agent@example.com"
    )
    edgar_filing_forms = str(provider_config.get("edgar_filing_forms", "10-K,10-Q"))
    edgar_filing_limit = int(provider_config.get("edgar_filing_limit", 8))

    for symbol in symbols:
        yahoo_symbol = to_yahoo_symbol(symbol)
        if include_price:
            tasks[f"equity.{symbol}.price_daily"] = (
                lambda s=yahoo_symbol: YahooPriceProvider().get_history(
                    PriceHistoryQuery(symbol=s, interval="d", limit=price_limit)
                )
            )
        if include_weekly:
            tasks[f"equity.{symbol}.price_weekly"] = (
                lambda s=yahoo_symbol: YahooPriceProvider().get_history(
                    PriceHistoryQuery(symbol=s, interval="w", limit=52)
                )
            )
        if include_stooq:
            tasks[f"equity.{symbol}.stooq_price_daily"] = (
                lambda s=symbol: StooqProvider().get_history(
                    PriceHistoryQuery(symbol=s, interval="d", limit=price_limit)
                )
            )
        if include_options and is_plain_us_equity(yahoo_symbol):
            tasks[f"equity.{symbol}.options_nearest"] = (
                lambda s=yahoo_symbol: YFinanceProvider().get_chain(
                    OptionsChainQuery(ticker=s)
                )
            )
        if include_edgar and is_plain_us_equity(yahoo_symbol):
            form4_limit = int(provider_config.get("edgar_form4_limit", 8))
            tasks[f"equity.{symbol}.edgar_form4"] = (
                lambda s=yahoo_symbol, limit=form4_limit: EdgarProvider(
                    user_email=edgar_user_email
                ).get_insider_transactions(EdgarInsiderQuery(ticker=s, limit=limit))
            )
        if include_edgar_filings and is_plain_us_equity(yahoo_symbol):
            tasks[f"equity.{symbol}.edgar_filings"] = (
                lambda s=yahoo_symbol, forms=edgar_filing_forms, limit=edgar_filing_limit: EdgarProvider(
                    user_email=edgar_user_email
                ).search_filings(EdgarSearchQuery(query=s, forms=forms, limit=limit))
            )
    return tasks
