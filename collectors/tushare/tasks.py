from __future__ import annotations

import re
from typing import Any, Callable

from collectors.tushare.client import settings_from_config
from collectors.tushare.provider import TushareProvider


TaskMap = dict[str, Callable[[], Any]]


def build_tushare_tasks(
    *,
    symbols: list[str],
    config: dict[str, Any],
    is_a_share_symbol: Callable[[str], bool],
) -> TaskMap:
    provider_config = dict(config.get("providers", {}).get("tushare", {}) or {})
    if provider_config.get("enabled", False) is False:
        return {}

    settings = settings_from_config(config)
    provider_cache: dict[str, TushareProvider] = {}

    def provider() -> TushareProvider:
        instance = provider_cache.get("provider")
        if instance is None:
            instance = TushareProvider(settings=settings)
            provider_cache["provider"] = instance
        return instance

    tasks: TaskMap = {}
    price_limit = int(provider_config.get("price_history_limit", config.get("price_history_limit", 90)))
    table_limit = int(provider_config.get("table_limit", 20))
    financial_limit = int(provider_config.get("financial_limit", 4))
    financial_period = optional_text(provider_config.get("financial_period"))
    market_trade_date = str(provider_config.get("trade_date", "20260515"))
    index_weight_trade_date = optional_text(provider_config.get("index_weight_trade_date"))
    macro_start_date = optional_text(provider_config.get("macro_start_date", "20240101"))
    macro_end_date = optional_text(provider_config.get("macro_end_date", "20260515"))
    macro_start_month = optional_text(provider_config.get("macro_start_month", "202401"))
    macro_end_month = optional_text(provider_config.get("macro_end_month", "202605"))
    a_share_symbols = [normalize_a_share_ts_code(symbol) for symbol in symbols if is_a_share_symbol(symbol)]
    global_symbols = [normalize_us_symbol(symbol) for symbol in symbols if not is_a_share_symbol(symbol)]

    def enabled(key: str, default: bool = False) -> bool:
        return bool(provider_config.get(key, default))

    if bool(provider_config.get("china_equity", True)):
        if enabled("stock_basic", False):
            tasks["tushare.stock_basic"] = (
                lambda limit=table_limit: provider().get_stock_basic(limit=limit)
            )
        if enabled("index_basic", True):
            tasks["tushare.index_basic"] = (
                lambda limit=table_limit: provider().get_index_basic(limit=limit)
            )
        for symbol in a_share_symbols:
            if enabled("a_share_daily", True):
                tasks[f"equity.{symbol}.tushare_price_daily"] = (
                    lambda s=symbol, limit=price_limit: provider().get_a_share_bars(
                        ts_code=s,
                        limit=limit,
                        freq="D",
                    )
                )
            if enabled("a_share_weekly", True):
                tasks[f"equity.{symbol}.tushare_price_weekly"] = (
                    lambda s=symbol: provider().get_a_share_bars(
                        ts_code=s,
                        limit=52,
                        freq="W",
                    )
                )
            if enabled("daily_basic", True):
                tasks[f"equity.{symbol}.tushare_daily_basic"] = (
                    lambda s=symbol: provider().get_daily_basic(ts_code=s, limit=1)
                )
            if enabled("a_share_financials", True):
                tasks[f"equity.{symbol}.tushare_income"] = (
                    lambda s=symbol, p=financial_period, limit=financial_limit: provider().get_income(
                        ts_code=s, period=p, limit=limit
                    )
                )
                tasks[f"equity.{symbol}.tushare_balancesheet"] = (
                    lambda s=symbol, p=financial_period, limit=financial_limit: provider().get_balancesheet(
                        ts_code=s, period=p, limit=limit
                    )
                )
                tasks[f"equity.{symbol}.tushare_cashflow"] = (
                    lambda s=symbol, p=financial_period, limit=financial_limit: provider().get_cashflow(
                        ts_code=s, period=p, limit=limit
                    )
                )
                tasks[f"equity.{symbol}.tushare_fina_indicator"] = (
                    lambda s=symbol, p=financial_period, limit=financial_limit: provider().get_fina_indicator(
                        ts_code=s, period=p, limit=limit
                    )
                )
                tasks[f"equity.{symbol}.tushare_dividend"] = (
                    lambda s=symbol, limit=financial_limit: provider().get_dividend(ts_code=s, limit=limit)
                )
                tasks[f"equity.{symbol}.tushare_disclosure_date"] = (
                    lambda s=symbol, limit=financial_limit: provider().get_disclosure_date(ts_code=s, limit=limit)
                )
                if enabled("forecast", False):
                    tasks[f"equity.{symbol}.tushare_forecast"] = (
                        lambda s=symbol, p=financial_period, limit=financial_limit: provider().get_forecast(
                            ts_code=s, period=p, limit=limit
                        )
                    )
                if enabled("express", False):
                    tasks[f"equity.{symbol}.tushare_express"] = (
                        lambda s=symbol, p=financial_period, limit=financial_limit: provider().get_express(
                            ts_code=s, period=p, limit=limit
                        )
                    )
            if enabled("moneyflow_lhb", True):
                if enabled("moneyflow", True):
                    tasks[f"equity.{symbol}.tushare_moneyflow"] = (
                        lambda s=symbol, limit=table_limit: provider().get_moneyflow(ts_code=s, limit=limit)
                    )
                if enabled("margin_detail", True):
                    tasks[f"equity.{symbol}.tushare_margin_detail"] = (
                        lambda s=symbol, limit=table_limit: provider().get_margin_detail(ts_code=s, limit=limit)
                    )

        index_symbols = tuple(provider_config.get("index_symbols", ("000001.SH", "399001.SZ", "399006.SZ", "000300.SH")))
        if enabled("index_daily", True):
            for index_symbol in index_symbols:
                normalized_index = normalize_a_share_ts_code(str(index_symbol))
                tasks[f"tushare.index.{normalized_index}.price_daily"] = (
                    lambda s=normalized_index, limit=price_limit: provider().get_index_bars(
                        ts_code=s,
                        limit=limit,
                    )
                )
                if enabled("index_etf", True) and enabled("index_dailybasic", True):
                    tasks[f"tushare.index.{normalized_index}.dailybasic"] = (
                        lambda s=normalized_index, limit=table_limit: provider().get_index_dailybasic(
                            ts_code=s, limit=limit
                        )
                    )
                if enabled("index_etf", True) and enabled("index_weight", True):
                    tasks[f"tushare.index.{normalized_index}.weight"] = (
                        lambda s=normalized_index, date=index_weight_trade_date, limit=table_limit: provider().get_index_weight(
                            index_code=s, trade_date=date, limit=limit
                        )
                    )

        if enabled("moneyflow_lhb", True):
            if enabled("moneyflow_hsgt", True):
                tasks["tushare.market.moneyflow_hsgt"] = (
                    lambda start=macro_start_date, end=macro_end_date, limit=table_limit: provider().get_moneyflow_hsgt(
                        start_date=start, end_date=end, limit=limit
                    )
                )
            if enabled("margin", True):
                tasks["tushare.margin"] = (
                    lambda date=market_trade_date, limit=table_limit: provider().get_margin(
                        trade_date=date, limit=limit
                    )
                )
            if enabled("top_list", True):
                tasks["tushare.lhb.top_list"] = (
                    lambda date=market_trade_date, limit=table_limit: provider().get_top_list(
                        trade_date=date, limit=limit
                    )
                )
            if enabled("top_inst", True):
                tasks["tushare.lhb.top_inst"] = (
                    lambda date=market_trade_date, limit=table_limit: provider().get_top_inst(
                        trade_date=date, limit=limit
                    )
                )

        if enabled("index_etf", True):
            if enabled("fund_basic", True):
                fund_market = optional_text(provider_config.get("fund_market", "E"))
                tasks["tushare.fund_basic"] = (
                    lambda market=fund_market, limit=table_limit: provider().get_fund_basic(
                        market=market, limit=limit
                    )
                )
            fund_symbols = tuple(provider_config.get("fund_symbols", ("510300.SH", "159919.SZ")))
            for fund_symbol in fund_symbols:
                normalized_fund = normalize_a_share_ts_code(str(fund_symbol))
                if enabled("fund_daily", True):
                    tasks[f"tushare.fund.{normalized_fund}.daily"] = (
                        lambda s=normalized_fund, limit=table_limit: provider().get_fund_daily(
                            ts_code=s, limit=limit
                        )
                    )
                if enabled("fund_nav", True):
                    tasks[f"tushare.fund.{normalized_fund}.nav"] = (
                        lambda s=normalized_fund, limit=table_limit: provider().get_fund_nav(
                            ts_code=s, limit=limit
                        )
                    )

        if enabled("futures_options", True):
            if enabled("fut_basic", True):
                futures_exchange = optional_text(provider_config.get("futures_exchange", "CFFEX"))
                tasks["tushare.futures.basic"] = (
                    lambda exchange=futures_exchange, limit=table_limit: provider().get_fut_basic(
                        exchange=exchange, limit=limit
                    )
                )
            futures_symbols = tuple(provider_config.get("futures_symbols", ("IF.CFX",)))
            for futures_symbol in futures_symbols:
                code = str(futures_symbol).upper()
                if enabled("fut_daily", True):
                    tasks[f"tushare.futures.{safe_task_label(code)}.daily"] = (
                        lambda s=code, limit=table_limit: provider().get_fut_daily(ts_code=s, limit=limit)
                    )
                if enabled("fut_mapping", True):
                    tasks[f"tushare.futures.{safe_task_label(code)}.mapping"] = (
                        lambda s=code, limit=table_limit: provider().get_fut_mapping(ts_code=s, limit=limit)
                    )
            if enabled("fut_holding", False):
                fut_holding_symbol = optional_text(provider_config.get("fut_holding_symbol"))
                tasks["tushare.futures.holding"] = (
                    lambda date=market_trade_date, symbol=fut_holding_symbol, limit=table_limit: provider().get_fut_holding(
                        trade_date=date, symbol=symbol, limit=limit
                    )
                )
            if enabled("opt_basic", True):
                option_exchange = optional_text(provider_config.get("option_exchange", "SSE"))
                tasks["tushare.options.basic"] = (
                    lambda exchange=option_exchange, limit=table_limit: provider().get_opt_basic(
                        exchange=exchange, limit=limit
                    )
                )
            option_symbols = tuple(provider_config.get("option_symbols", ()))
            if enabled("opt_daily", False):
                for option_symbol in option_symbols:
                    code = str(option_symbol).upper()
                    tasks[f"tushare.options.{safe_task_label(code)}.daily"] = (
                        lambda s=code, limit=table_limit: provider().get_opt_daily(ts_code=s, limit=limit)
                    )

    if enabled("macro_rates", True):
        if enabled("shibor", True):
            tasks["tushare.macro.shibor"] = (
                lambda start=macro_start_date, end=macro_end_date, limit=table_limit: provider().get_shibor(
                    start_date=start, end_date=end, limit=limit
                )
            )
        if enabled("cn_gdp", True):
            tasks["tushare.macro.cn_gdp"] = (
                lambda limit=table_limit: provider().get_cn_gdp(limit=limit)
            )
        if enabled("cn_cpi", True):
            tasks["tushare.macro.cn_cpi"] = (
                lambda start=macro_start_month, end=macro_end_month, limit=table_limit: provider().get_cn_cpi(
                    start_m=start, end_m=end, limit=limit
                )
            )
        if enabled("cn_pmi", True):
            tasks["tushare.macro.cn_pmi"] = (
                lambda start=macro_start_month, end=macro_end_month, limit=table_limit: provider().get_cn_pmi(
                    start_m=start, end_m=end, limit=limit
                )
            )
        if enabled("us_tycr", True):
            tasks["tushare.macro.us_tycr"] = (
                lambda start=macro_start_date, end=macro_end_date, limit=table_limit: provider().get_us_tycr(
                    start_date=start, end_date=end, limit=limit
                )
            )
        if enabled("us_trycr", True):
            tasks["tushare.macro.us_trycr"] = (
                lambda start=macro_start_date, end=macro_end_date, limit=table_limit: provider().get_us_trycr(
                    start_date=start, end_date=end, limit=limit
                )
            )
        if enabled("us_tbr", True):
            tasks["tushare.macro.us_tbr"] = (
                lambda start=macro_start_date, end=macro_end_date, limit=table_limit: provider().get_us_tbr(
                    start_date=start, end_date=end, limit=limit
                )
            )
        if enabled("us_tltr", True):
            tasks["tushare.macro.us_tltr"] = (
                lambda start=macro_start_date, end=macro_end_date, limit=table_limit: provider().get_us_tltr(
                    start_date=start, end_date=end, limit=limit
                )
            )
        if enabled("us_trltr", True):
            tasks["tushare.macro.us_trltr"] = (
                lambda start=macro_start_date, end=macro_end_date, limit=table_limit: provider().get_us_trltr(
                    start_date=start, end_date=end, limit=limit
                )
            )

    if bool(provider_config.get("us_equity", True)):
        if bool(provider_config.get("us_basic", True)):
            tasks["tushare.us_basic"] = (
                lambda limit=table_limit: provider().get_us_basic(limit=limit)
            )
        if bool(provider_config.get("us_daily", True)):
            for symbol in global_symbols:
                if not symbol:
                    continue
                tasks[f"equity.{symbol}.tushare_us_daily"] = (
                    lambda s=symbol, limit=price_limit: provider().get_us_daily(
                        ts_code=s,
                        limit=limit,
                    )
                )

    if bool(provider_config.get("crypto", True)):
        if bool(provider_config.get("coinlist", False)):
            start_date = str(provider_config.get("coinlist_start_date", "20170101"))
            end_date = str(provider_config.get("coinlist_end_date", "20171231"))
            tasks["tushare.crypto.coinlist"] = (
                lambda start=start_date, end=end_date, limit=table_limit: provider().get_coinlist(
                    start_date=start,
                    end_date=end,
                    limit=limit,
                )
            )
        if bool(provider_config.get("coincap", True)):
            trade_date = str(provider_config.get("coincap_trade_date", "20180806"))
            coins = tuple(provider_config.get("coincap_coins", ("BTC", "ETH")))
            for coin in coins:
                coin_text = str(coin).upper()
                tasks[f"tushare.crypto.coincap.{safe_task_label(coin_text)}"] = (
                    lambda c=coin_text, date=trade_date, limit=table_limit: provider().get_coincap(
                        trade_date=date,
                        coin=c,
                        limit=limit,
                    )
                )
        if bool(provider_config.get("coin_bar", False)):
            exchange = str(provider_config.get("coin_bar_exchange", "okex"))
            ts_code = str(provider_config.get("coin_bar_ts_code", "BTC_USDT"))
            freq = str(provider_config.get("coin_bar_freq", "1min"))
            start_date = str(provider_config.get("coin_bar_start_date", "2020-04-01 00:00:01"))
            end_date = str(provider_config.get("coin_bar_end_date", "2020-04-04 19:00:00"))
            tasks[f"tushare.crypto.coin_bar.{safe_task_label(exchange)}.{safe_task_label(ts_code)}"] = (
                lambda ex=exchange, code=ts_code, fr=freq, start=start_date, end=end_date, limit=table_limit: provider().get_coin_bar(
                    exchange=ex,
                    ts_code=code,
                    freq=fr,
                    start_date=start,
                    end_date=end,
                    limit=limit,
                )
            )

    return tasks


def normalize_a_share_ts_code(symbol: str) -> str:
    normalized = symbol.strip().upper()
    lowered = normalized.lower()
    if re.fullmatch(r"(sh|sz|bj)\d{6}", lowered):
        return f"{normalized[2:]}.{normalized[:2]}"
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", normalized):
        return normalized
    if re.fullmatch(r"\d{6}", normalized):
        if normalized.startswith(("6", "5", "9")):
            return f"{normalized}.SH"
        if normalized.startswith(("4", "8")):
            return f"{normalized}.BJ"
        return f"{normalized}.SZ"
    return normalized


def normalize_us_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.endswith(".US"):
        return normalized[:-3]
    return normalized


def optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def safe_task_label(value: object) -> str:
    return str(value).replace(" ", "_").replace("/", "_").replace(".", "_")[:80]
