from __future__ import annotations

from typing import Any, Callable


TaskMap = dict[str, Callable[[], Any]]


def build_macro_tasks(*, config: dict[str, Any]) -> TaskMap:
    from collectors.digital_oracle import (
        BisCreditGapQuery,
        BisProvider,
        BisRateQuery,
        CftcCotProvider,
        CftcCotQuery,
        CMEFedWatchProvider,
        ExchangeRateQuery,
        FearGreedProvider,
        PriceHistoryQuery,
        USTreasuryProvider,
        WorldBankProvider,
        WorldBankQuery,
        YahooPriceProvider,
        YieldCurveQuery,
    )

    provider_config = dict(config.get("providers", {}).get("macro", {}))
    if provider_config.get("enabled", config.get("include_macro", True)) is False:
        return {}

    tasks: TaskMap = {}
    if bool(provider_config.get("treasury", True)):
        tasks["macro.yield_curve"] = lambda: USTreasuryProvider().latest_yield_curve()
        curve_kinds = tuple(provider_config.get("treasury_curve_kinds", ("real", "bill", "long_term")))
        for curve_kind in curve_kinds:
            tasks[f"macro.treasury.{curve_kind}_curve"] = (
                lambda kind=str(curve_kind): USTreasuryProvider().latest_yield_curve(
                    YieldCurveQuery(curve_kind=kind)
                )
            )
        if bool(provider_config.get("treasury_exchange_rates", True)):
            countries = tuple(provider_config.get("treasury_exchange_rate_countries", ("China", "Japan")))
            exchange_limit = int(provider_config.get("treasury_exchange_rate_limit", 12))
            tasks["macro.treasury.exchange_rates"] = (
                lambda c=countries, limit=exchange_limit: USTreasuryProvider().list_exchange_rates(
                    ExchangeRateQuery(countries=c, limit=limit)
                )
            )
    if bool(provider_config.get("fear_greed", True)):
        tasks["macro.fear_greed"] = lambda: FearGreedProvider().get_index()
    if bool(provider_config.get("cme_fedwatch", True)):
        tasks["macro.cme_fedwatch"] = lambda: CMEFedWatchProvider().get_probabilities()

    macro_symbols = tuple(
        provider_config.get(
            "price_symbols",
            config.get("macro_symbols", ("SPY", "QQQ", "^VIX", "GC=F", "USDCNY=X")),
        )
    )
    for macro_symbol in macro_symbols:
        tasks[f"macro.price.{macro_symbol}"] = (
            lambda s=macro_symbol: YahooPriceProvider().get_history(
                PriceHistoryQuery(symbol=s, interval="d", limit=60)
            )
        )

    if bool(provider_config.get("cftc", True)):
        cftc_commodities = tuple(provider_config.get("cftc_commodities", ("GOLD", "CRUDE OIL", "S&P 500")))
        cftc_limit = int(provider_config.get("cftc_limit", 8))
        for commodity in cftc_commodities:
            safe_label = str(commodity).replace(" ", "_").replace("&", "and")
            tasks[f"macro.cftc.{safe_label}"] = (
                lambda c=commodity, limit=cftc_limit: CftcCotProvider().list_reports(
                    CftcCotQuery(commodity_name=str(c), limit=limit)
                )
            )

    if bool(provider_config.get("bis", False)):
        countries = tuple(provider_config.get("bis_countries", ("US", "CN")))
        start_year = int(provider_config.get("bis_start_year", 2020))
        credit_start_year = int(provider_config.get("bis_credit_start_year", 2018))
        tasks["macro.bis.policy_rates"] = lambda: BisProvider().get_policy_rates(
            BisRateQuery(countries=countries, start_year=start_year)
        )
        tasks["macro.bis.credit_gap"] = lambda: BisProvider().get_credit_to_gdp(
            BisCreditGapQuery(countries=countries, start_year=credit_start_year)
        )

    if bool(provider_config.get("worldbank", False)):
        countries = tuple(provider_config.get("worldbank_countries", ("US", "CN")))
        date_range = str(provider_config.get("worldbank_date_range", "2018:2026"))
        indicators = tuple(
            provider_config.get(
                "worldbank_indicators",
                ("NY.GDP.MKTP.CD", "FP.CPI.TOTL.ZG", "FR.INR.RINR"),
            )
        )
        for indicator in indicators:
            tasks[f"macro.worldbank.{indicator}"] = (
                lambda i=indicator: WorldBankProvider().get_indicator(
                    WorldBankQuery(indicator=str(i), countries=countries, date_range=date_range)
                )
            )

    return tasks
