from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from collectors.digital_oracle.providers.prices import PriceBar, PriceHistory
from collectors.tushare.client import TushareSettings, create_pro_api


@dataclass(frozen=True)
class TushareTable:
    table: str
    rows: tuple[dict[str, object], ...]
    provider_id: str = "tushare"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TushareDailyBasic:
    ts_code: str
    trade_date: str | None
    turnover_rate: float | None = None
    volume_ratio: float | None = None
    pe: float | None = None
    pb: float | None = None
    total_market_cap_cny_100m: float | None = None
    float_market_cap_cny_100m: float | None = None
    raw: dict[str, object] = field(default_factory=dict, repr=False)


class TushareProvider:
    provider_id = "tushare"
    display_name = "Tushare Pro"

    def __init__(self, *, settings: TushareSettings, api: Any | None = None, ts_module: Any | None = None) -> None:
        self.settings = settings
        self._ts_module = ts_module
        self.pro = api or create_pro_api(settings, ts_module=ts_module)

    def get_stock_basic(self, *, limit: int = 20) -> TushareTable:
        df = self.pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,area,industry,list_date",
            limit=limit,
        )
        return table_from_dataframe("stock_basic", df, limit=limit)

    def get_index_basic(self, *, limit: int = 20) -> TushareTable:
        df = self.pro.index_basic(limit=limit)
        return table_from_dataframe("index_basic", df, limit=limit)

    def get_table(self, table: str, *, limit: int = 20, **kwargs: object) -> TushareTable:
        api_kwargs = {key: value for key, value in kwargs.items() if value not in (None, "")}
        api_kwargs["limit"] = limit
        df = getattr(self.pro, table)(**api_kwargs)
        return table_from_dataframe(table, df, limit=limit, metadata=kwargs)

    def get_a_share_bars(self, *, ts_code: str, limit: int, freq: str = "D") -> PriceHistory:
        ts_module = self._require_ts_module()
        df = ts_module.pro_bar(api=self.pro, ts_code=ts_code, limit=limit, freq=freq)
        return price_history_from_dataframe(
            df,
            symbol=ts_code,
            raw_symbol=ts_code,
            interval=tushare_interval_label(freq),
        )

    def get_index_bars(self, *, ts_code: str, limit: int) -> PriceHistory:
        df = self.pro.index_daily(ts_code=ts_code, limit=limit)
        return price_history_from_dataframe(
            df,
            symbol=ts_code,
            raw_symbol=ts_code,
            interval="day",
        )

    def get_daily_basic(self, *, ts_code: str, limit: int = 1) -> tuple[TushareDailyBasic, ...]:
        df = self.pro.daily_basic(
            ts_code=ts_code,
            fields="ts_code,trade_date,turnover_rate,volume_ratio,pe,pb,total_mv,circ_mv",
            limit=limit,
        )
        rows = dataframe_records(df, limit=limit)
        return tuple(daily_basic_from_row(row) for row in rows)

    def get_income(self, *, ts_code: str, period: str | None = None, limit: int = 4) -> TushareTable:
        return self.get_table("income", ts_code=ts_code, period=period, limit=limit)

    def get_balancesheet(self, *, ts_code: str, period: str | None = None, limit: int = 4) -> TushareTable:
        return self.get_table("balancesheet", ts_code=ts_code, period=period, limit=limit)

    def get_cashflow(self, *, ts_code: str, period: str | None = None, limit: int = 4) -> TushareTable:
        return self.get_table("cashflow", ts_code=ts_code, period=period, limit=limit)

    def get_fina_indicator(self, *, ts_code: str, period: str | None = None, limit: int = 4) -> TushareTable:
        return self.get_table("fina_indicator", ts_code=ts_code, period=period, limit=limit)

    def get_dividend(self, *, ts_code: str, limit: int = 4) -> TushareTable:
        return self.get_table("dividend", ts_code=ts_code, limit=limit)

    def get_disclosure_date(self, *, ts_code: str, limit: int = 4) -> TushareTable:
        return self.get_table("disclosure_date", ts_code=ts_code, limit=limit)

    def get_forecast(self, *, ts_code: str, period: str | None = None, limit: int = 4) -> TushareTable:
        return self.get_table("forecast", ts_code=ts_code, period=period, limit=limit)

    def get_express(self, *, ts_code: str, period: str | None = None, limit: int = 4) -> TushareTable:
        return self.get_table("express", ts_code=ts_code, period=period, limit=limit)

    def get_moneyflow(self, *, ts_code: str, limit: int = 5) -> TushareTable:
        return self.get_table("moneyflow", ts_code=ts_code, limit=limit)

    def get_moneyflow_hsgt(self, *, start_date: str | None = None, end_date: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("moneyflow_hsgt", start_date=start_date, end_date=end_date, limit=limit)

    def get_margin(self, *, trade_date: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("margin", trade_date=trade_date, limit=limit)

    def get_margin_detail(self, *, ts_code: str, limit: int = 5) -> TushareTable:
        return self.get_table("margin_detail", ts_code=ts_code, limit=limit)

    def get_top_list(self, *, trade_date: str, limit: int = 20) -> TushareTable:
        return self.get_table("top_list", trade_date=trade_date, limit=limit)

    def get_top_inst(self, *, trade_date: str, limit: int = 20) -> TushareTable:
        return self.get_table("top_inst", trade_date=trade_date, limit=limit)

    def get_index_weight(self, *, index_code: str, trade_date: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("index_weight", index_code=index_code, trade_date=trade_date, limit=limit)

    def get_index_dailybasic(self, *, ts_code: str, limit: int = 20) -> TushareTable:
        return self.get_table("index_dailybasic", ts_code=ts_code, limit=limit)

    def get_fund_basic(self, *, market: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("fund_basic", market=market, limit=limit)

    def get_fund_daily(self, *, ts_code: str, limit: int = 20) -> TushareTable:
        return self.get_table("fund_daily", ts_code=ts_code, limit=limit)

    def get_fund_nav(self, *, ts_code: str, limit: int = 20) -> TushareTable:
        return self.get_table("fund_nav", ts_code=ts_code, limit=limit)

    def get_fut_basic(self, *, exchange: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("fut_basic", exchange=exchange, limit=limit)

    def get_fut_daily(self, *, ts_code: str, limit: int = 20) -> TushareTable:
        return self.get_table("fut_daily", ts_code=ts_code, limit=limit)

    def get_fut_mapping(self, *, ts_code: str, limit: int = 20) -> TushareTable:
        return self.get_table("fut_mapping", ts_code=ts_code, limit=limit)

    def get_fut_holding(self, *, trade_date: str, symbol: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("fut_holding", trade_date=trade_date, symbol=symbol, limit=limit)

    def get_opt_basic(self, *, exchange: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("opt_basic", exchange=exchange, limit=limit)

    def get_opt_daily(self, *, ts_code: str, limit: int = 20) -> TushareTable:
        return self.get_table("opt_daily", ts_code=ts_code, limit=limit)

    def get_shibor(self, *, start_date: str | None = None, end_date: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("shibor", start_date=start_date, end_date=end_date, limit=limit)

    def get_cn_gdp(self, *, limit: int = 20) -> TushareTable:
        return self.get_table("cn_gdp", limit=limit)

    def get_cn_cpi(self, *, start_m: str | None = None, end_m: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("cn_cpi", start_m=start_m, end_m=end_m, limit=limit)

    def get_cn_pmi(self, *, start_m: str | None = None, end_m: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("cn_pmi", start_m=start_m, end_m=end_m, limit=limit)

    def get_us_tycr(self, *, start_date: str | None = None, end_date: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("us_tycr", start_date=start_date, end_date=end_date, limit=limit)

    def get_us_trycr(self, *, start_date: str | None = None, end_date: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("us_trycr", start_date=start_date, end_date=end_date, limit=limit)

    def get_us_tbr(self, *, start_date: str | None = None, end_date: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("us_tbr", start_date=start_date, end_date=end_date, limit=limit)

    def get_us_tltr(self, *, start_date: str | None = None, end_date: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("us_tltr", start_date=start_date, end_date=end_date, limit=limit)

    def get_us_trltr(self, *, start_date: str | None = None, end_date: str | None = None, limit: int = 20) -> TushareTable:
        return self.get_table("us_trltr", start_date=start_date, end_date=end_date, limit=limit)

    def get_us_basic(self, *, limit: int = 20) -> TushareTable:
        df = self.pro.us_basic(limit=limit)
        return table_from_dataframe("us_basic", df, limit=limit)

    def get_us_daily(self, *, ts_code: str, limit: int = 90) -> PriceHistory:
        df = self.pro.us_daily(ts_code=ts_code)
        return price_history_from_dataframe(
            df,
            symbol=ts_code,
            raw_symbol=ts_code,
            interval="day",
            limit=limit,
        )

    def get_coinlist(self, *, start_date: str, end_date: str, limit: int = 20) -> TushareTable:
        df = self.pro.coinlist(start_date=start_date, end_date=end_date)
        return table_from_dataframe("coinlist", df, limit=limit)

    def get_coincap(self, *, trade_date: str, coin: str | None = None, limit: int = 20) -> TushareTable:
        kwargs = {"trade_date": trade_date}
        if coin:
            kwargs["coin"] = coin
        df = self.pro.coincap(**kwargs)
        return table_from_dataframe("coincap", df, limit=limit, metadata=kwargs)

    def get_coin_bar(
        self,
        *,
        exchange: str,
        ts_code: str,
        freq: str,
        start_date: str,
        end_date: str,
        limit: int = 20,
    ) -> TushareTable:
        df = self.pro.coin_bar(
            exchange=exchange,
            ts_code=ts_code,
            freq=freq,
            start_date=start_date,
            end_date=end_date,
        )
        return table_from_dataframe(
            "coin_bar",
            df,
            limit=limit,
            metadata={
                "exchange": exchange,
                "ts_code": ts_code,
                "freq": freq,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    def _require_ts_module(self) -> Any:
        if self._ts_module is not None:
            return self._ts_module
        import tushare as ts_module

        self._ts_module = ts_module
        return ts_module


def table_from_dataframe(
    table: str,
    df: Any,
    *,
    limit: int,
    metadata: dict[str, object] | None = None,
) -> TushareTable:
    return TushareTable(
        table=table,
        rows=tuple(dataframe_records(df, limit=limit)),
        metadata=dict(metadata or {}),
    )


def price_history_from_dataframe(
    df: Any,
    *,
    symbol: str,
    raw_symbol: str,
    interval: str,
    limit: int | None = None,
) -> PriceHistory:
    rows = dataframe_records(df, limit=limit)
    bars: list[PriceBar] = []
    for row in rows:
        date = normalize_trade_date(row.get("trade_date") or row.get("date") or row.get("datetime"))
        open_price = to_float(row.get("open"))
        high_price = to_float(row.get("high"))
        low_price = to_float(row.get("low"))
        close_price = to_float(row.get("close"))
        if date is None or None in (open_price, high_price, low_price, close_price):
            continue
        bars.append(
            PriceBar(
                date=date,
                open=float(open_price),
                high=float(high_price),
                low=float(low_price),
                close=float(close_price),
                volume=to_float(row.get("vol") or row.get("volume")),
            )
        )
    bars.sort(key=lambda bar: bar.date)
    return PriceHistory(
        symbol=symbol,
        raw_symbol=raw_symbol,
        interval=interval,
        bars=tuple(bars),
        provider_id="tushare",
    )


def daily_basic_from_row(row: dict[str, object]) -> TushareDailyBasic:
    return TushareDailyBasic(
        ts_code=str(row.get("ts_code") or ""),
        trade_date=normalize_trade_date(row.get("trade_date")),
        turnover_rate=to_float(row.get("turnover_rate")),
        volume_ratio=to_float(row.get("volume_ratio")),
        pe=to_float(row.get("pe")),
        pb=to_float(row.get("pb")),
        total_market_cap_cny_100m=market_cap_100m(row.get("total_mv")),
        float_market_cap_cny_100m=market_cap_100m(row.get("circ_mv")),
        raw=row,
    )


def dataframe_records(df: Any, *, limit: int | None = None) -> list[dict[str, object]]:
    if df is None:
        return []
    if hasattr(df, "empty") and bool(getattr(df, "empty")):
        return []
    if not hasattr(df, "to_dict"):
        if isinstance(df, dict):
            rows = [df]
        elif isinstance(df, (list, tuple)):
            rows = [item if isinstance(item, dict) else {"value": item} for item in df]
        else:
            rows = [{"value": df}]
    else:
        rows = df.to_dict("records")
    if limit is not None:
        rows = rows[:limit]
    return [{str(key): clean_value(value) for key, value in dict(row).items()} for row in rows]


def clean_value(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def normalize_trade_date(value: object | None) -> str | None:
    if value is None or value == "":
        return None
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def to_float(value: object | None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def market_cap_100m(value: object | None) -> float | None:
    number = to_float(value)
    if number is None:
        return None
    return round(number / 10000, 4)


def tushare_interval_label(freq: str) -> str:
    normalized = freq.strip().upper()
    if normalized == "W":
        return "week"
    if normalized == "M":
        return "month"
    return "day"
