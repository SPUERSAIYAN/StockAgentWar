from __future__ import annotations

import re
import json
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ._a_share import normalize_tencent_a_share_symbol
from ._coerce import _coerce_float
from .base import ProviderParseError, SignalProvider


TENCENT_FINANCE_QUOTE_URL = "https://qt.gtimg.cn/q="
TENCENT_STOCK_APP_URL = "https://web.ifzq.gtimg.cn/appstock/app"
_QUOTE_RE = re.compile(r'v_([^=]+)="(.*)";?')


class TencentTextClient(Protocol):
    def get_text(self, url: str, *, params: Mapping[str, object] | None = None) -> str: ...


@dataclass
class TencentGbkTextClient:
    timeout_seconds: float = 10.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 0.5
    headers: Mapping[str, str] = field(
        default_factory=lambda: {
            "Accept": "text/plain,*/*",
            "User-Agent": "digital-oracle/0.1",
            "Referer": "https://finance.qq.com/",
        }
    )

    def get_text(self, url: str, *, params: Mapping[str, object] | None = None) -> str:
        del params
        request = Request(url, headers=dict(self.headers))
        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    data = response.read()
                return data.decode("gb18030", errors="replace")
            except HTTPError:
                raise
            except (URLError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self.retry_attempts:
                    break
                time.sleep(self.retry_delay_seconds)
        raise RuntimeError(f"request failed: {url}") from last_error


@dataclass(frozen=True)
class TencentStockMetricsQuery:
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class TencentBoardQuery:
    path: str
    params: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TencentStockMetrics:
    market_kind: str | None
    symbol: str
    code: str
    name: str | None
    price: float | None
    previous_close: float | None
    open: float | None
    high: float | None
    low: float | None
    change: float | None
    change_pct: float | None
    volume_lots: float | None
    amount_cny_10k: float | None
    turnover_rate: float | None
    pe: float | None
    pb: float | None
    float_market_cap_cny_100m: float | None
    total_market_cap_cny_100m: float | None
    amplitude_pct: float | None
    volume_ratio: float | None
    limit_up: float | None
    limit_down: float | None
    timestamp: str | None
    raw_fields: tuple[str, ...] = field(default_factory=tuple, repr=False)


def _field(fields: list[str], index: int) -> str | None:
    if index >= len(fields):
        return None
    value = fields[index]
    if value == "":
        return None
    return value


def _market_kind(value: str | None, symbol: str) -> str | None:
    if symbol.startswith("sh000") or symbol.startswith("sz399"):
        return "index"
    if symbol.startswith(("sh", "sz", "bj")):
        return "a_share"
    if value == "1":
        return "index_or_a_share"
    if value == "100":
        return "hk"
    if value == "200":
        return "us"
    return None


def _field_float(fields: list[str], index: int) -> float | None:
    return _coerce_float(_field(fields, index))


def _parse_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) >= 14 and value[:14].isdigit():
        return (
            f"{value[:4]}-{value[4:6]}-{value[6:8]} "
            f"{value[8:10]}:{value[10:12]}:{value[12:14]}"
        )
    return value


def _parse_line(line: str) -> TencentStockMetrics | None:
    line = line.strip()
    if not line:
        return None
    match = _QUOTE_RE.match(line)
    if not match:
        raise ProviderParseError(f"unexpected Tencent Finance quote line: {line[:80]}")

    symbol = match.group(1)
    fields = match.group(2).split("~")
    if len(fields) < 4:
        return None

    return TencentStockMetrics(
        market_kind=_market_kind(_field(fields, 0), symbol),
        symbol=symbol,
        code=_field(fields, 2) or symbol[-6:],
        name=_field(fields, 1),
        price=_field_float(fields, 3),
        previous_close=_field_float(fields, 4),
        open=_field_float(fields, 5),
        high=_field_float(fields, 33),
        low=_field_float(fields, 34),
        change=_field_float(fields, 31),
        change_pct=_field_float(fields, 32),
        volume_lots=_field_float(fields, 36) or _field_float(fields, 6),
        amount_cny_10k=_field_float(fields, 37),
        turnover_rate=_field_float(fields, 38),
        pe=_field_float(fields, 39),
        pb=_field_float(fields, 46),
        float_market_cap_cny_100m=_field_float(fields, 44),
        total_market_cap_cny_100m=_field_float(fields, 45),
        amplitude_pct=_field_float(fields, 43),
        volume_ratio=_field_float(fields, 49),
        limit_up=_field_float(fields, 47),
        limit_down=_field_float(fields, 48),
        timestamp=_parse_timestamp(_field(fields, 30)),
        raw_fields=tuple(fields),
    )


def _normalize_tencent_symbol(symbol: str) -> str:
    normalized = symbol.strip()
    lowered = normalized.lower()
    if lowered.startswith(("sh", "sz", "bj", "hk", "us", "r_", "gb_")):
        return normalized
    if "." in normalized:
        code, suffix = normalized.split(".", 1)
        suffix = suffix.lower()
        if suffix in {"sh", "sz", "bj"}:
            return normalize_tencent_a_share_symbol(normalized)
        if suffix == "hk":
            return f"hk{code.zfill(5)}"
        if suffix in {"us", "oq", "n", "ny", "nasdaq", "nyse"}:
            return f"us{code.upper()}"
    return normalize_tencent_a_share_symbol(normalized)


def _build_url(url: str, params: Mapping[str, object] | None) -> str:
    if not params:
        return url
    query = urlencode(
        [(key, str(value)) for key, value in params.items() if value is not None]
    )
    if not query:
        return url
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}{query}"


class TencentFinanceProvider(SignalProvider):
    provider_id = "tencent_finance"
    display_name = "Tencent Finance A-Share"
    capabilities = (
        "a_share_realtime_metrics",
        "a_share_valuation",
        "a_share_market_cap",
        "a_share_turnover",
        "a_share_volume_ratio",
        "index_quotes",
        "hk_quotes",
        "us_quotes",
        "board_raw_data",
    )

    def __init__(self, http_client: TencentTextClient | None = None) -> None:
        self.http_client = http_client or TencentGbkTextClient()

    def get_stock_metrics(
        self,
        query: TencentStockMetricsQuery | str | Sequence[str],
    ) -> tuple[TencentStockMetrics, ...]:
        if isinstance(query, TencentStockMetricsQuery):
            raw_symbols = query.symbols
        elif isinstance(query, str):
            raw_symbols = (query,)
        else:
            raw_symbols = tuple(query)

        symbols = tuple(_normalize_tencent_symbol(symbol) for symbol in raw_symbols)
        url = f"{TENCENT_FINANCE_QUOTE_URL}{','.join(symbols)}"
        payload = self.http_client.get_text(url)
        if not isinstance(payload, str):
            raise ProviderParseError("expected Tencent Finance response to be text")

        metrics: list[TencentStockMetrics] = []
        for line in payload.splitlines():
            parsed = _parse_line(line)
            if parsed is not None:
                metrics.append(parsed)
        return tuple(metrics)

    def get_realtime_quotes(
        self,
        symbols: str | Sequence[str],
    ) -> tuple[TencentStockMetrics, ...]:
        return self.get_stock_metrics(symbols)

    def get_index_metrics(
        self,
        symbols: str | Sequence[str] = ("sh000001", "sz399001", "sz399006"),
    ) -> tuple[TencentStockMetrics, ...]:
        return self.get_stock_metrics(symbols)

    def get_hk_metrics(
        self,
        symbols: str | Sequence[str],
    ) -> tuple[TencentStockMetrics, ...]:
        return self.get_stock_metrics(symbols)

    def get_us_metrics(
        self,
        symbols: str | Sequence[str],
    ) -> tuple[TencentStockMetrics, ...]:
        return self.get_stock_metrics(symbols)

    def fetch_board_raw(self, query: TencentBoardQuery) -> str:
        path = query.path.strip()
        url = path if path.startswith(("http://", "https://")) else f"{TENCENT_STOCK_APP_URL}/{path.lstrip('/')}"
        return self.http_client.get_text(_build_url(url, query.params))

    def fetch_board_json_like(self, query: TencentBoardQuery) -> Any:
        text = self.fetch_board_raw(query)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
