from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from ._a_share import strip_a_share_exchange
from ._coerce import _coerce_float, _coerce_int
from .base import ProviderError, ProviderParseError, SignalProvider
from .prices import PriceBar, PriceHistory


_FREQUENCY_MAP: dict[str, int] = {
    "5m": 0,
    "5min": 0,
    "15m": 1,
    "15min": 1,
    "30m": 2,
    "30min": 2,
    "1h": 3,
    "60m": 3,
    "day": 9,
    "daily": 9,
    "d": 9,
    "1d": 9,
    "week": 5,
    "weekly": 5,
    "w": 5,
    "1w": 5,
    "month": 6,
    "monthly": 6,
    "mon": 6,
    "m": 6,
    "1m": 8,
    "1min": 8,
    "quarter": 10,
    "3mon": 10,
    "year": 11,
    "y": 11,
}

_FREQUENCY_LABELS = {
    0: "5m",
    1: "15m",
    2: "30m",
    3: "1h",
    4: "day",
    5: "week",
    6: "month",
    7: "1m",
    8: "1m",
    9: "day",
    10: "quarter",
    11: "year",
}


class MootdxClient(Protocol):
    def bars(
        self,
        *,
        symbol: str,
        frequency: int,
        start: int = 0,
        offset: int = 800,
        **kwargs: Any,
    ) -> Any: ...

    def index(
        self,
        *,
        symbol: str,
        frequency: int,
        start: int = 0,
        offset: int = 800,
        **kwargs: Any,
    ) -> Any: ...

    def quotes(self, symbol: str | Sequence[str], **kwargs: Any) -> Any: ...

    def minute(self, symbol: str, **kwargs: Any) -> Any: ...

    def minutes(self, symbol: str, date: str, **kwargs: Any) -> Any: ...

    def transaction(
        self,
        symbol: str,
        start: int = 0,
        offset: int = 800,
        **kwargs: Any,
    ) -> Any: ...

    def transactions(
        self,
        symbol: str,
        start: int = 0,
        offset: int = 800,
        date: str = "",
        **kwargs: Any,
    ) -> Any: ...

    def xdxr(self, symbol: str, **kwargs: Any) -> Any: ...

    def finance(self, symbol: str, **kwargs: Any) -> Any: ...

    def stocks(self, market: int, **kwargs: Any) -> Any: ...

    def stock_count(self, market: int) -> int: ...

    def k(self, symbol: str, begin: str, end: str, **kwargs: Any) -> Any: ...

    def F10(self, symbol: str, name: str = "") -> Any: ...  # noqa: N802

    def F10C(self, symbol: str) -> Any: ...  # noqa: N802


@dataclass(frozen=True)
class MootdxBarQuery:
    symbol: str
    frequency: str | int = "day"
    start: int = 0
    offset: int = 800
    adjust: str | None = None
    is_index: bool = False


@dataclass(frozen=True)
class MootdxDateRangeQuery:
    symbol: str
    begin: str
    end: str
    adjust: str | None = None


@dataclass(frozen=True)
class MootdxIntradayQuery:
    symbol: str
    date: str | None = None


@dataclass(frozen=True)
class MootdxTransactionQuery:
    symbol: str
    start: int = 0
    offset: int = 800
    date: str | None = None


@dataclass(frozen=True)
class MootdxLocalDataQuery:
    symbol: str
    tdxdir: str
    frequency: str = "day"
    market: str = "std"


@dataclass(frozen=True)
class MootdxRealtimeQuote:
    symbol: str
    name: str | None
    price: float | None
    previous_close: float | None
    open: float | None
    high: float | None
    low: float | None
    volume: float | None
    amount: float | None
    bid1: float | None = None
    ask1: float | None = None
    raw: dict[str, object] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class MootdxOrderLevel:
    level: int
    bid_price: float | None
    bid_volume: float | None
    ask_price: float | None
    ask_volume: float | None


@dataclass(frozen=True)
class MootdxOrderBook:
    symbol: str
    name: str | None
    levels: tuple[MootdxOrderLevel, ...]
    raw: dict[str, object] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class MootdxIntradayPoint:
    time: str | None
    price: float | None
    average_price: float | None = None
    volume: float | None = None
    amount: float | None = None
    raw: dict[str, object] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class MootdxTransaction:
    time: str | None
    price: float | None
    volume: float | None
    amount: float | None
    direction: str | None
    raw: dict[str, object] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class MootdxCorporateAction:
    date: str | None
    category: str | None
    dividend: float | None
    allotment_price: float | None
    shares_bonus: float | None
    shares_transfer: float | None
    raw: dict[str, object] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class MootdxStockInfo:
    symbol: str
    name: str | None
    pre_close: float | None = None
    raw: dict[str, object] = field(default_factory=dict, repr=False)


@dataclass
class MootdxFinancialSummary:
    symbol: str
    updated_date: str | None
    ipo_date: str | None
    eps: float | None
    eps_source: str | None
    net_profit: float | None
    revenue: float | None
    operating_profit: float | None
    total_assets: float | None
    net_assets: float | None
    total_share_capital: float | None
    float_share_capital: float | None
    book_value_per_share: float | None
    shareholders: int | None
    raw: dict[str, object] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class MootdxShareholderSnapshot:
    symbol: str
    shareholders: int | None
    total_share_capital: float | None
    float_share_capital: float | None
    raw: dict[str, object] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class MootdxCompanyProfileQuery:
    symbol: str
    sections: tuple[str, ...] = ("公司概况", "公司简介", "最新提示")
    include_all: bool = False


@dataclass
class MootdxCompanyProfile:
    symbol: str
    sections: dict[str, str]

    @property
    def overview(self) -> str | None:
        for name in ("公司概况", "公司简介", "最新提示"):
            text = self.sections.get(name)
            if text:
                return text
        if not self.sections:
            return None
        return next(iter(self.sections.values()))


class _MootdxClientFactory:
    def __init__(
        self,
        *,
        market: str = "std",
        server: Sequence[object] | None = None,
        multithread: bool = True,
        heartbeat: bool = True,
        bestip: bool = False,
        timeout: int = 15,
    ) -> None:
        try:
            quotes_module = importlib.import_module("mootdx.quotes")
        except ImportError:
            deps_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                os.pardir,
                os.pardir,
                ".deps",
            )
            if os.path.isdir(deps_path) and deps_path not in sys.path:
                sys.path.insert(0, deps_path)
            try:
                quotes_module = importlib.import_module("mootdx.quotes")
            except ImportError as exc:
                raise ImportError(
                    "mootdx is required for MootdxProvider but is not installed.\n"
                    "Install it with:  uv pip install --target .deps mootdx"
                ) from exc

        self._client = quotes_module.Quotes.factory(
            market=market,
            server=server,
            multithread=multithread,
            heartbeat=heartbeat,
            bestip=bestip,
            timeout=timeout,
        )

    def client(self) -> MootdxClient:
        return self._client


class _MootdxReaderFactory:
    def __init__(self, *, market: str, tdxdir: str) -> None:
        try:
            reader_module = importlib.import_module("mootdx.reader")
        except ImportError:
            deps_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                os.pardir,
                os.pardir,
                ".deps",
            )
            if os.path.isdir(deps_path) and deps_path not in sys.path:
                sys.path.insert(0, deps_path)
            try:
                reader_module = importlib.import_module("mootdx.reader")
            except ImportError as exc:
                raise ImportError(
                    "mootdx is required for local TDX reader access but is not installed.\n"
                    "Install it with:  uv pip install --target .deps mootdx"
                ) from exc
        self._reader = reader_module.Reader.factory(market=market, tdxdir=tdxdir)

    def reader(self) -> Any:
        return self._reader


def _frequency_code(value: str | int) -> int:
    if isinstance(value, int):
        if value in _FREQUENCY_LABELS:
            return value
        raise ValueError(f"unsupported mootdx frequency: {value!r}")
    normalized = value.strip().lower()
    if normalized in _FREQUENCY_MAP:
        return _FREQUENCY_MAP[normalized]
    raise ValueError(
        f"unsupported mootdx frequency: {value!r} "
        "(use day/week/month/1m/5m/15m/30m/1h or a TDX frequency code)"
    )


def _records(payload: Any) -> list[dict[str, object]]:
    if payload is None:
        return []

    if hasattr(payload, "empty") and bool(getattr(payload, "empty")):
        return []

    if hasattr(payload, "to_dict"):
        try:
            data = payload.to_dict("records")
            if isinstance(data, list):
                return [_record(item) for item in data]
        except TypeError:
            pass

    if isinstance(payload, dict):
        return [_record(payload)]

    if isinstance(payload, (list, tuple)):
        return [_record(item) for item in payload]

    return [_record(payload)]


def _record(value: Any) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): inner for key, inner in value.items()}
    if hasattr(value, "_asdict"):
        return {str(key): inner for key, inner in value._asdict().items()}
    if hasattr(value, "__dict__"):
        return {str(key): inner for key, inner in vars(value).items()}
    return {"value": value}


def _first_value(row: dict[str, object], names: tuple[str, ...]) -> object | None:
    lowered = {key.lower(): value for key, value in row.items()}
    for name in names:
        if name in row:
            return row[name]
        lowered_name = name.lower()
        if lowered_name in lowered:
            return lowered[lowered_name]
    return None


def _first_float(row: dict[str, object], names: tuple[str, ...]) -> float | None:
    return _coerce_float(_first_value(row, names))


def _first_int(row: dict[str, object], names: tuple[str, ...]) -> int | None:
    return _coerce_int(_first_value(row, names))


def _string_or_none(value: object | None) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _bar_date(row: dict[str, object]) -> str | None:
    value = _first_value(row, ("date", "datetime", "time"))
    if value is not None:
        if hasattr(value, "strftime"):
            text = value.strftime("%Y-%m-%d %H:%M:%S")
            return text.replace(" 00:00:00", "")
        return str(value)

    year = _first_int(row, ("year",))
    month = _first_int(row, ("month",))
    day = _first_int(row, ("day",))
    if year and month and day:
        hour = _first_int(row, ("hour",)) or 0
        minute = _first_int(row, ("minute",)) or 0
        if hour or minute:
            return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _parse_time(row: dict[str, object]) -> str | None:
    value = _first_value(row, ("time", "datetime", "date", "trade_time"))
    if value is None:
        hour = _first_int(row, ("hour",))
        minute = _first_int(row, ("minute",))
        if hour is not None and minute is not None:
            return f"{hour:02d}:{minute:02d}:00"
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S").replace("1900-01-01 ", "")
    text = str(value)
    if text.isdigit() and len(text) <= 6:
        return text.zfill(6)
    return text


def _parse_bars(rows: list[dict[str, object]]) -> tuple[PriceBar, ...]:
    bars: list[PriceBar] = []
    for row in rows:
        date = _bar_date(row)
        open_price = _first_float(row, ("open",))
        high_price = _first_float(row, ("high",))
        low_price = _first_float(row, ("low",))
        close_price = _first_float(row, ("close",))
        if date is None or any(
            value is None
            for value in (open_price, high_price, low_price, close_price)
        ):
            continue
        bars.append(
            PriceBar(
                date=date,
                open=float(open_price),
                high=float(high_price),
                low=float(low_price),
                close=float(close_price),
                volume=_first_float(row, ("volume", "vol")),
            )
        )
    return tuple(bars)


def _parse_intraday(rows: list[dict[str, object]]) -> tuple[MootdxIntradayPoint, ...]:
    points: list[MootdxIntradayPoint] = []
    for row in rows:
        price = _first_float(row, ("price", "close", "now"))
        average = _first_float(row, ("avg_price", "average_price", "avprice"))
        points.append(
            MootdxIntradayPoint(
                time=_parse_time(row),
                price=price,
                average_price=average,
                volume=_first_float(row, ("volume", "vol")),
                amount=_first_float(row, ("amount", "turnover")),
                raw=row,
            )
        )
    return tuple(points)


def _parse_transactions(rows: list[dict[str, object]]) -> tuple[MootdxTransaction, ...]:
    transactions: list[MootdxTransaction] = []
    for row in rows:
        transactions.append(
            MootdxTransaction(
                time=_parse_time(row),
                price=_first_float(row, ("price",)),
                volume=_first_float(row, ("volume", "vol")),
                amount=_first_float(row, ("amount", "turnover")),
                direction=_string_or_none(
                    _first_value(row, ("buyorsell", "direction", "side", "bsflag"))
                ),
                raw=row,
            )
        )
    return tuple(transactions)


def _parse_corporate_actions(rows: list[dict[str, object]]) -> tuple[MootdxCorporateAction, ...]:
    actions: list[MootdxCorporateAction] = []
    for row in rows:
        actions.append(
            MootdxCorporateAction(
                date=_string_or_none(_first_value(row, ("date", "datetime", "time"))),
                category=_string_or_none(_first_value(row, ("category", "type", "name"))),
                dividend=_first_float(row, ("cash", "fenhong", "dividend")),
                allotment_price=_first_float(row, ("peiguprice", "allotment_price")),
                shares_bonus=_first_float(row, ("songzhuangu", "songgu", "shares_bonus")),
                shares_transfer=_first_float(row, ("zhuanzeng", "shares_transfer")),
                raw=row,
            )
        )
    return tuple(actions)


def _parse_stocks(rows: list[dict[str, object]]) -> tuple[MootdxStockInfo, ...]:
    stocks: list[MootdxStockInfo] = []
    for row in rows:
        symbol = _string_or_none(_first_value(row, ("code", "symbol")))
        if not symbol:
            continue
        stocks.append(
            MootdxStockInfo(
                symbol=symbol,
                name=_string_or_none(_first_value(row, ("name",))),
                pre_close=_first_float(row, ("pre_close", "last_close", "close")),
                raw=row,
            )
        )
    return tuple(stocks)


def _parse_quote(row: dict[str, object], fallback_symbol: str | None = None) -> MootdxRealtimeQuote:
    symbol = _string_or_none(_first_value(row, ("symbol", "code"))) or fallback_symbol
    if not symbol:
        raise ProviderParseError("mootdx quote row is missing symbol/code")
    return MootdxRealtimeQuote(
        symbol=symbol,
        name=_string_or_none(_first_value(row, ("name",))),
        price=_first_float(row, ("price", "now", "last_price")),
        previous_close=_first_float(row, ("last_close", "pre_close", "prev_close", "previous_close")),
        open=_first_float(row, ("open",)),
        high=_first_float(row, ("high",)),
        low=_first_float(row, ("low",)),
        volume=_first_float(row, ("volume", "vol")),
        amount=_first_float(row, ("amount", "turnover")),
        bid1=_first_float(row, ("bid1", "bid_1")),
        ask1=_first_float(row, ("ask1", "ask_1")),
        raw=row,
    )


def _parse_order_book(row: dict[str, object], fallback_symbol: str | None = None) -> MootdxOrderBook:
    symbol = _string_or_none(_first_value(row, ("symbol", "code"))) or fallback_symbol
    if not symbol:
        raise ProviderParseError("mootdx order book row is missing symbol/code")
    levels = []
    for level in range(1, 6):
        levels.append(
            MootdxOrderLevel(
                level=level,
                bid_price=_first_float(row, (f"bid{level}", f"bid_{level}", f"b{level}_p")),
                bid_volume=_first_float(row, (f"bid_vol{level}", f"bid{level}_vol", f"bid{level}_volume", f"b{level}_v")),
                ask_price=_first_float(row, (f"ask{level}", f"ask_{level}", f"a{level}_p")),
                ask_volume=_first_float(row, (f"ask_vol{level}", f"ask{level}_vol", f"ask{level}_volume", f"a{level}_v")),
            )
        )
    return MootdxOrderBook(
        symbol=symbol,
        name=_string_or_none(_first_value(row, ("name",))),
        levels=tuple(levels),
        raw=row,
    )


def _eps_from_row(row: dict[str, object]) -> tuple[float | None, str | None]:
    explicit_eps = _first_float(
        row,
        (
            "eps",
            "basic_eps",
            "jbmgsy",
            "meigushouyi",
            "mei_gu_shou_yi",
            "fn1",
            "FN1",
        ),
    )
    if explicit_eps is not None:
        return explicit_eps, "reported"

    net_profit = _first_float(row, ("jinglirun", "jing_li_run"))
    total_shares = _first_float(row, ("zongguben", "zong_gu_ben", "total_share_capital"))
    if net_profit is not None and total_shares not in (None, 0):
        return net_profit / float(total_shares), "net_profit/total_share_capital"
    return None, None


class MootdxProvider(SignalProvider):
    provider_id = "mootdx"
    display_name = "MooTDX A-Share"
    capabilities = (
        "a_share_price_history",
        "a_share_intraday",
        "a_share_transactions",
        "a_share_order_book",
        "a_share_realtime_quotes",
        "a_share_fundamentals",
        "a_share_company_profile",
        "a_share_stock_list",
        "a_share_local_tdx",
    )

    def __init__(self, *, client: MootdxClient | None = None, **factory_options: Any) -> None:
        self._client = client or _MootdxClientFactory(**factory_options).client()

    def get_bars(self, query: MootdxBarQuery) -> PriceHistory:
        symbol = strip_a_share_exchange(query.symbol)
        frequency = _frequency_code(query.frequency)
        kwargs: dict[str, object] = {}
        if query.adjust:
            kwargs["adjust"] = query.adjust

        if query.is_index:
            payload = self._client.index(
                symbol=symbol,
                frequency=frequency,
                start=query.start,
                offset=query.offset,
                **kwargs,
            )
        else:
            payload = self._client.bars(
                symbol=symbol,
                frequency=frequency,
                start=query.start,
                offset=query.offset,
                **kwargs,
            )

        bars = _parse_bars(_records(payload))
        return PriceHistory(
            symbol=symbol,
            raw_symbol=query.symbol,
            interval=_FREQUENCY_LABELS.get(frequency, str(frequency)),
            provider_id=self.provider_id,
            bars=bars,
            metadata={
                "frequency": frequency,
                "is_index": query.is_index,
                "adjust": query.adjust,
            },
        )

    def get_ohlc_range(self, query: MootdxDateRangeQuery) -> PriceHistory:
        symbol = strip_a_share_exchange(query.symbol)
        kwargs: dict[str, object] = {}
        if query.adjust:
            kwargs["adjust"] = query.adjust
        payload = self._client.k(
            symbol=symbol,
            begin=query.begin,
            end=query.end,
            **kwargs,
        )
        return PriceHistory(
            symbol=symbol,
            raw_symbol=query.symbol,
            interval="day",
            provider_id=self.provider_id,
            bars=_parse_bars(_records(payload)),
            metadata={"begin": query.begin, "end": query.end, "adjust": query.adjust},
        )

    def get_realtime_quotes(self, symbols: str | Sequence[str]) -> tuple[MootdxRealtimeQuote, ...]:
        if isinstance(symbols, str):
            normalized_symbols = [strip_a_share_exchange(symbols)]
        else:
            normalized_symbols = [strip_a_share_exchange(symbol) for symbol in symbols]

        payload = self._client.quotes(
            symbol=normalized_symbols[0] if len(normalized_symbols) == 1 else normalized_symbols
        )
        rows = _records(payload)
        quotes: list[MootdxRealtimeQuote] = []
        for index, row in enumerate(rows):
            fallback_symbol = normalized_symbols[index] if index < len(normalized_symbols) else None
            quotes.append(_parse_quote(row, fallback_symbol=fallback_symbol))
        return tuple(quotes)

    def get_order_books(self, symbols: str | Sequence[str]) -> tuple[MootdxOrderBook, ...]:
        if isinstance(symbols, str):
            normalized_symbols = [strip_a_share_exchange(symbols)]
        else:
            normalized_symbols = [strip_a_share_exchange(symbol) for symbol in symbols]
        payload = self._client.quotes(
            symbol=normalized_symbols[0] if len(normalized_symbols) == 1 else normalized_symbols
        )
        books: list[MootdxOrderBook] = []
        for index, row in enumerate(_records(payload)):
            fallback_symbol = normalized_symbols[index] if index < len(normalized_symbols) else None
            books.append(_parse_order_book(row, fallback_symbol=fallback_symbol))
        return tuple(books)

    def get_intraday_points(self, query: MootdxIntradayQuery | str) -> tuple[MootdxIntradayPoint, ...]:
        if isinstance(query, str):
            query = MootdxIntradayQuery(symbol=query)
        symbol = strip_a_share_exchange(query.symbol)
        if query.date:
            payload = self._client.minutes(symbol=symbol, date=query.date)
        else:
            payload = self._client.minute(symbol=symbol)
        return _parse_intraday(_records(payload))

    def get_transactions(self, query: MootdxTransactionQuery | str) -> tuple[MootdxTransaction, ...]:
        if isinstance(query, str):
            query = MootdxTransactionQuery(symbol=query)
        symbol = strip_a_share_exchange(query.symbol)
        if query.date:
            payload = self._client.transactions(
                symbol=symbol,
                start=query.start,
                offset=query.offset,
                date=query.date,
            )
        else:
            payload = self._client.transaction(
                symbol=symbol,
                start=query.start,
                offset=query.offset,
            )
        return _parse_transactions(_records(payload))

    def get_corporate_actions(self, symbol: str) -> tuple[MootdxCorporateAction, ...]:
        normalized_symbol = strip_a_share_exchange(symbol)
        return _parse_corporate_actions(_records(self._client.xdxr(symbol=normalized_symbol)))

    def list_stocks(self, market: str | int = "sh") -> tuple[MootdxStockInfo, ...]:
        market_code = _market_code(market)
        return _parse_stocks(_records(self._client.stocks(market=market_code)))

    def get_stock_count(self, market: str | int = "sh") -> int:
        return int(self._client.stock_count(market=_market_code(market)))

    def get_financial_summary(self, symbol: str) -> MootdxFinancialSummary:
        normalized_symbol = strip_a_share_exchange(symbol)
        rows = _records(self._client.finance(symbol=normalized_symbol))
        if not rows:
            raise ProviderError(f"mootdx returned no financial data for {symbol}")
        row = rows[0]
        eps, eps_source = _eps_from_row(row)
        return MootdxFinancialSummary(
            symbol=normalized_symbol,
            updated_date=_string_or_none(_first_value(row, ("updated_date", "updatedDate"))),
            ipo_date=_string_or_none(_first_value(row, ("ipo_date", "ipoDate"))),
            eps=eps,
            eps_source=eps_source,
            net_profit=_first_float(row, ("jinglirun", "jing_li_run")),
            revenue=_first_float(row, ("zhuyingshouru", "zhu_ying_shou_ru")),
            operating_profit=_first_float(row, ("yingyelirun", "yingye_li_run")),
            total_assets=_first_float(row, ("zongzichan", "zong_zi_chan")),
            net_assets=_first_float(row, ("jingzichan", "jing_zi_chan")),
            total_share_capital=_first_float(row, ("zongguben", "zong_gu_ben")),
            float_share_capital=_first_float(row, ("liutongguben", "liu_tong_gu_ben")),
            book_value_per_share=_first_float(row, ("meigujingzichan", "mei_gu_jing_zi_chan")),
            shareholders=_first_int(row, ("gudongrenshu", "gu_dong_ren_shu")),
            raw=row,
        )

    def get_shareholder_snapshot(self, symbol: str) -> MootdxShareholderSnapshot:
        summary = self.get_financial_summary(symbol)
        return MootdxShareholderSnapshot(
            symbol=summary.symbol,
            shareholders=summary.shareholders,
            total_share_capital=summary.total_share_capital,
            float_share_capital=summary.float_share_capital,
            raw=summary.raw,
        )

    def read_local_bars(self, query: MootdxLocalDataQuery) -> PriceHistory:
        symbol = strip_a_share_exchange(query.symbol)
        reader = _MootdxReaderFactory(market=query.market, tdxdir=query.tdxdir).reader()
        frequency = query.frequency.strip().lower()
        if frequency in {"day", "daily", "d", "1d"}:
            payload = reader.daily(symbol=symbol)
            interval = "day"
        elif frequency in {"5m", "5min"}:
            payload = reader.fzline(symbol=symbol)
            interval = "5m"
        elif frequency in {"1m", "1min"}:
            payload = reader.minute(symbol=symbol, suffix="1")
            interval = "1m"
        else:
            raise ValueError("local TDX reader supports day, 1m, and 5m")
        return PriceHistory(
            symbol=symbol,
            raw_symbol=query.symbol,
            interval=interval,
            provider_id=self.provider_id,
            bars=_parse_bars(_records(payload)),
            metadata={"tdxdir": query.tdxdir, "local": True, "market": query.market},
        )

    def list_company_sections(self, symbol: str) -> tuple[str, ...]:
        normalized_symbol = strip_a_share_exchange(symbol)
        rows = _records(self._client.F10C(symbol=normalized_symbol))
        sections: list[str] = []
        for row in rows:
            name = _string_or_none(_first_value(row, ("name",)))
            if name:
                sections.append(name)
        return tuple(sections)

    def get_company_profile(
        self,
        query: MootdxCompanyProfileQuery | str,
    ) -> MootdxCompanyProfile:
        if isinstance(query, str):
            query = MootdxCompanyProfileQuery(symbol=query)

        symbol = strip_a_share_exchange(query.symbol)
        sections: dict[str, str] = {}
        if query.include_all:
            payload = self._client.F10(symbol=symbol)
            if isinstance(payload, dict):
                for name, text in payload.items():
                    if text:
                        sections[str(name)] = str(text)
            elif payload:
                sections["全部"] = str(payload)
            return MootdxCompanyProfile(symbol=symbol, sections=sections)

        for section in query.sections:
            payload = self._client.F10(symbol=symbol, name=section)
            if payload:
                sections[section] = str(payload)
        return MootdxCompanyProfile(symbol=symbol, sections=sections)


def _market_code(market: str | int) -> int:
    if isinstance(market, int):
        if market in (0, 1):
            return market
        raise ValueError("market must be 0/SZ or 1/SH")
    normalized = market.strip().lower()
    if normalized in {"sz", "0", "shen", "shenzhen"}:
        return 0
    if normalized in {"sh", "1", "shanghai"}:
        return 1
    raise ValueError("market must be 'sh' or 'sz'")
