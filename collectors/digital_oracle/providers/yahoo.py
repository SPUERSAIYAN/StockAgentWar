"""Yahoo Finance price history provider.

Replaces the Stooq provider with Yahoo Finance as the data source for
OHLCV price history.  Supports stocks, ETFs, futures, forex and indices.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .base import ProviderError, ProviderParseError, SignalProvider
from .prices import PriceBar, PriceHistory, PriceHistoryQuery
from ._yahoo_guard import guarded_yahoo_request

# Map PriceHistoryQuery interval codes to yfinance interval strings
_INTERVAL_MAP = {"d": "1d", "w": "1wk", "m": "1mo"}


def _limit_to_period(limit: int | None, interval: str) -> str:
    """Convert a bar *limit* into a yfinance ``period`` string.

    yfinance uses period strings like ``"1mo"``, ``"6mo"`` etc. rather than
    explicit row counts, so we approximate conservatively.
    """
    if limit is None or limit <= 0:
        return "max"

    if interval in ("w", "1wk"):
        days = limit * 7
    elif interval in ("m", "1mo"):
        days = limit * 31
    else:
        days = limit

    # Add generous padding so we never under-fetch
    days = int(days * 1.5) + 10

    if days <= 7:
        return "5d"
    if days <= 30:
        return "1mo"
    if days <= 90:
        return "3mo"
    if days <= 180:
        return "6mo"
    if days <= 365:
        return "1y"
    if days <= 730:
        return "2y"
    if days <= 1825:
        return "5y"
    if days <= 3650:
        return "10y"
    return "max"


# ---------------------------------------------------------------------------
# Fetcher protocol (for testability)
# ---------------------------------------------------------------------------


class PriceFetcher(Protocol):
    """Abstracts raw price data retrieval so tests can supply a fake."""

    def fetch_history(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
    ) -> list[dict[str, Any]]: ...


class _YahooChartPriceFetcher:
    """Default fetcher backed by Yahoo's chart endpoint."""

    _BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    def fetch_history(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
    ) -> list[dict[str, Any]]:
        payload = guarded_yahoo_request(
            lambda: self._fetch_chart_payload(symbol, period=period, interval=interval)
        )
        return self._parse_chart_payload(payload, symbol=symbol)

    def _fetch_chart_payload(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
    ) -> dict[str, Any]:
        encoded_symbol = quote(symbol, safe="")
        params = urlencode(
            {
                "range": period,
                "interval": interval,
                "events": "history",
                "includePrePost": "false",
            }
        )
        url = f"{self._BASE_URL}/{encoded_symbol}?{params}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
                ),
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as exc:
            raise ProviderError(
                f"Yahoo chart request failed with HTTP {exc.code}: {url}"
            ) from exc
        except (TimeoutError, URLError) as exc:
            raise ProviderError(f"Yahoo chart request failed: {url}") from exc
        except json.JSONDecodeError as exc:
            raise ProviderParseError(f"invalid Yahoo chart JSON for {symbol}") from exc

    def _parse_chart_payload(
        self,
        payload: dict[str, Any],
        *,
        symbol: str,
    ) -> list[dict[str, Any]]:
        chart = payload.get("chart")
        if not isinstance(chart, dict):
            raise ProviderParseError(f"invalid Yahoo chart payload for {symbol}")
        errors = chart.get("error")
        if errors:
            raise ProviderError(f"Yahoo chart error for {symbol}: {errors}")
        results = chart.get("result")
        if not isinstance(results, list) or not results:
            raise ProviderParseError(f"empty Yahoo chart result for {symbol}")

        result = results[0]
        if not isinstance(result, dict):
            raise ProviderParseError(f"invalid Yahoo chart result for {symbol}")
        timestamps = result.get("timestamp")
        indicators = result.get("indicators")
        if not isinstance(timestamps, list) or not isinstance(indicators, dict):
            raise ProviderParseError(f"missing Yahoo chart bars for {symbol}")
        quotes = indicators.get("quote")
        if not isinstance(quotes, list) or not quotes or not isinstance(quotes[0], dict):
            raise ProviderParseError(f"missing Yahoo chart quote data for {symbol}")

        quote_data = quotes[0]
        rows: list[dict[str, Any]] = []
        for index, timestamp in enumerate(timestamps):
            if timestamp is None:
                continue
            rows.append(
                {
                    "Date": datetime.fromtimestamp(
                        int(timestamp), timezone.utc
                    ).date(),
                    "Open": _list_get(quote_data.get("open"), index),
                    "High": _list_get(quote_data.get("high"), index),
                    "Low": _list_get(quote_data.get("low"), index),
                    "Close": _list_get(quote_data.get("close"), index),
                    "Volume": _list_get(quote_data.get("volume"), index),
                }
            )
        return rows


def _list_get(values: Any, index: int) -> Any:
    if not isinstance(values, list) or index >= len(values):
        return None
    value = values[index]
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class YahooPriceProvider(SignalProvider):
    """Yahoo Finance OHLCV price history provider.

    Drop-in replacement for StooqProvider.  Uses Yahoo Finance symbols
    (e.g. ``GC=F`` for gold, ``CL=F`` for crude oil, ``SPY`` for S&P 500
    ETF, ``EURUSD=X`` for EUR/USD forex).

    Uses Yahoo's chart endpoint directly instead of yfinance's cookie/crumb path.
    """

    provider_id = "yahoo"
    display_name = "Yahoo Finance Prices"
    capabilities = ("price_history",)

    def __init__(self, *, fetcher: PriceFetcher | None = None) -> None:
        self._fetcher: PriceFetcher = fetcher or _YahooChartPriceFetcher()

    def get_history(self, query: PriceHistoryQuery) -> PriceHistory:
        interval = query.interval.lower().strip()
        yf_interval = _INTERVAL_MAP.get(interval)
        if yf_interval is None:
            raise ValueError(
                f"unsupported interval: {query.interval!r} (use 'd', 'w', or 'm')"
            )

        symbol = query.symbol.strip()
        period = _limit_to_period(query.limit, interval)

        raw_rows = self._fetcher.fetch_history(
            symbol, period=period, interval=yf_interval
        )

        bars: list[PriceBar] = []
        for row in raw_rows:
            dt = row.get("Date")
            if dt is None:
                continue

            # Format date as YYYY-MM-DD string
            date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]

            if query.start_date and date_str < query.start_date:
                continue
            if query.end_date and date_str > query.end_date:
                continue

            open_price = row.get("Open")
            high_price = row.get("High")
            low_price = row.get("Low")
            close_price = row.get("Close")

            if any(v is None for v in (open_price, high_price, low_price, close_price)):
                continue

            volume_raw = row.get("Volume")
            volume = float(volume_raw) if volume_raw is not None else None

            bars.append(
                PriceBar(
                    date=date_str,
                    open=float(open_price),
                    high=float(high_price),
                    low=float(low_price),
                    close=float(close_price),
                    volume=volume,
                )
            )

        if query.limit is not None and query.limit >= 0:
            bars = bars[-query.limit:]

        if not bars:
            raise ProviderParseError(
                f"Yahoo Finance returned no usable {interval} bars for {symbol}"
            )

        return PriceHistory(
            symbol=symbol,
            raw_symbol=query.symbol,
            interval=interval,
            provider_id=self.provider_id,
            bars=tuple(bars),
        )
