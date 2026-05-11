from __future__ import annotations

import math
import re
import sys
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from collectors.connectors.china import build_china_equity_tasks
from collectors.connectors.crypto import build_crypto_tasks
from collectors.connectors.equity import build_equity_tasks
from collectors.connectors.macro import build_macro_tasks
from collectors.connectors.prediction import build_prediction_market_tasks
from collectors.connectors.web_search import build_web_search_tasks
from schemas.state import AgentRuntimeConfig, MarketDecisionState


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_MARKET_INFORMATION_DIR = PROJECT_ROOT / "external" / "Market-Information-Skill"
DEFAULT_COLLECTOR_CONFIG: dict[str, Any] = {
    "enabled": True,
    "timeout_seconds": 35,
    "max_workers": 12,
    "price_history_limit": 90,
    "include_macro": True,
    "include_options": True,
    "include_edgar": True,
    "include_a_share_metrics": True,
    "macro_symbols": ("SPY", "QQQ", "^VIX", "GC=F", "USDCNY=X"),
    "providers": {
        "us_equity": {
            "enabled": True,
            "price": True,
            "weekly_price": True,
            "options": True,
            "edgar": True,
            "stooq_compat": False,
        },
        "china_equity": {
            "enabled": True,
            "tencent": True,
            "mootdx": False,
        },
        "macro": {
            "enabled": True,
            "treasury": True,
            "fear_greed": True,
            "cme_fedwatch": True,
            "cftc": True,
            "bis": False,
            "worldbank": False,
        },
        "prediction_markets": {
            "enabled": True,
            "kalshi": True,
            "polymarket": True,
        },
        "crypto": {
            "enabled": True,
            "coingecko": True,
            "deribit": True,
        },
        "web_search": {
            "enabled": False,
        },
    },
}


def collect_market_information(
    state: MarketDecisionState,
    config: AgentRuntimeConfig,
) -> dict[str, Any] | None:
    collector_config = merge_dicts(DEFAULT_COLLECTOR_CONFIG, dict(config.get("collector", {})))
    if collector_config.get("enabled", False) is False:
        return None
    if not (VENDOR_MARKET_INFORMATION_DIR / "digital_oracle").exists():
        return None

    ensure_external_market_information_path()

    try:
        from digital_oracle import gather
    except Exception as exc:
        return {
            "collection_status": "unavailable",
            "generated_at": now_iso(),
            "sources": {},
            "errors": {"digital_oracle_import": f"{type(exc).__name__}: {exc}"},
        }

    symbols = extract_candidate_symbols(state)
    if not symbols:
        return {
            "collection_status": "empty",
            "generated_at": now_iso(),
            "sources": {},
            "errors": {"symbols": "未提供候选股票代码，无法调用市场数据 provider。"},
        }

    timeout_seconds = float(collector_config.get("timeout_seconds", 35))
    max_workers = int(collector_config.get("max_workers", 12))

    tasks: dict[str, Any] = {}
    a_share_symbols = [symbol for symbol in symbols if is_a_share_symbol(symbol)]
    global_symbols = [symbol for symbol in symbols if symbol not in a_share_symbols]

    tasks.update(
        build_equity_tasks(
            symbols=global_symbols,
            config=collector_config,
            is_plain_us_equity=is_plain_us_equity,
            to_yahoo_symbol=to_yahoo_symbol,
        )
    )
    tasks.update(build_china_equity_tasks(symbols=a_share_symbols, config=collector_config))
    tasks.update(build_macro_tasks(config=collector_config))
    tasks.update(
        build_prediction_market_tasks(
            task=state.get("task", ""),
            symbols=symbols,
            config=collector_config,
        )
    )
    tasks.update(build_crypto_tasks(config=collector_config))
    tasks.update(
        build_web_search_tasks(
            task=state.get("task", ""),
            symbols=symbols,
            config=collector_config,
        )
    )

    gathered = gather(
        tasks,
        max_workers=max_workers,
        timeout_seconds=timeout_seconds,
        fail_fast=False,
    )
    return summarize_gathered_market_data(
        task=state.get("task", ""),
        symbols=symbols,
        results=gathered.results,
        errors=gathered.errors,
    )


def ensure_external_market_information_path() -> None:
    external_path = str(VENDOR_MARKET_INFORMATION_DIR)
    if VENDOR_MARKET_INFORMATION_DIR.exists() and external_path not in sys.path:
        sys.path.insert(0, external_path)


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def extract_candidate_symbols(state: MarketDecisionState) -> list[str]:
    seen: set[str] = set()
    symbols: list[str] = []
    for candidate in state.get("candidates", []):
        symbol = str(candidate.get("symbol", "")).strip()
        if not symbol:
            continue
        normalized = symbol.upper()
        if normalized not in seen:
            seen.add(normalized)
            symbols.append(normalized)
    return symbols


def summarize_gathered_market_data(
    *,
    task: str,
    symbols: list[str],
    results: dict[str, Any],
    errors: dict[str, BaseException],
) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for label, value in results.items():
        sources[label] = summarize_provider_value(value)

    rendered_errors = {
        label: f"{type(exc).__name__}: {exc}" for label, exc in errors.items()
    }
    if results and rendered_errors:
        status = "partial"
    elif results:
        status = "ok"
    else:
        status = "failed"

    return {
        "collection_status": status,
        "generated_at": now_iso(),
        "task": task,
        "symbols": symbols,
        "source_count": len(results),
        "error_count": len(rendered_errors),
        "sources": sources,
        "errors": rendered_errors,
    }


def summarize_provider_value(value: Any) -> Any:
    class_name = value.__class__.__name__
    if hasattr(value, "bars"):
        return summarize_price_history(value)
    if isinstance(value, (list, tuple)):
        return summarize_sequence(value)
    if class_name == "OptionsChain":
        return summarize_options_chain(value)
    if class_name == "DeribitOptionChain":
        return summarize_deribit_option_chain(value)
    if class_name == "DeribitFuturesTermStructure":
        return summarize_deribit_futures_curve(value)
    if class_name == "EdgarInsiderSummary":
        return summarize_edgar_insider(value)
    if class_name == "YieldCurveSnapshot":
        return summarize_yield_curve(value)
    if class_name == "FearGreedSnapshot":
        return to_jsonable(value)
    if class_name == "WorldBankResult":
        return summarize_worldbank_result(value)
    if class_name == "WebSearchResult":
        return summarize_web_search_result(value)
    return to_jsonable(value)


def summarize_sequence(values: Any, *, limit: int = 20) -> dict[str, Any]:
    items = list(values or ())
    class_name = items[0].__class__.__name__ if items else ""
    if class_name == "TencentStockMetrics":
        rendered = [summarize_tencent_metrics(item) for item in items[:limit]]
    elif class_name == "FedMeetingProbability":
        rendered = [summarize_fed_meeting(item) for item in items[:limit]]
    else:
        rendered = [summarize_provider_value(item) for item in items[:limit]]
    return {
        "item_type": class_name,
        "item_count": len(items),
        "items": rendered,
        "truncated": len(items) > limit,
    }


def summarize_price_history(history: Any) -> dict[str, Any]:
    bars = list(getattr(history, "bars", ()) or ())
    latest = bars[-1] if bars else None
    earliest = bars[0] if bars else None
    closes = [float(bar.close) for bar in bars if getattr(bar, "close", None) is not None]
    volumes = [
        float(bar.volume)
        for bar in bars[-20:]
        if getattr(bar, "volume", None) not in (None, 0)
    ]
    return {
        "provider": getattr(history, "provider_id", ""),
        "symbol": getattr(history, "symbol", ""),
        "raw_symbol": getattr(history, "raw_symbol", ""),
        "interval": getattr(history, "interval", ""),
        "bar_count": len(bars),
        "earliest": to_jsonable(earliest),
        "latest": to_jsonable(latest),
        "return_total_pct": percent_change(
            getattr(earliest, "close", None),
            getattr(latest, "close", None),
        ),
        "return_20_bar_pct": percent_change(
            closes[-21] if len(closes) >= 21 else None,
            closes[-1] if closes else None,
        ),
        "high_20": max((float(getattr(bar, "high", 0)) for bar in bars[-20:]), default=None),
        "low_20": min((float(getattr(bar, "low", 0)) for bar in bars[-20:]), default=None),
        "avg_volume_20": safe_average(volumes),
        "realized_vol_20_annualized": realized_volatility(closes[-21:]),
    }


def summarize_options_chain(chain: Any) -> dict[str, Any]:
    return {
        "ticker": getattr(chain, "ticker", ""),
        "expiration": getattr(chain, "expiration", ""),
        "underlying_price": getattr(chain, "underlying_price", None),
        "atm_strike": chain.atm_strike,
        "atm_iv": chain.atm_iv,
        "implied_move": chain.implied_move(),
        "put_call_volume_ratio": chain.put_call_volume_ratio,
        "put_call_oi_ratio": chain.put_call_oi_ratio,
        "total_volume": chain.total_volume,
        "total_open_interest": chain.total_open_interest,
        "max_pain": chain.max_pain(),
    }


def summarize_deribit_option_chain(chain: Any) -> dict[str, Any]:
    strikes = list(getattr(chain, "strikes", ()) or ())
    atm = chain.atm_strike()
    return {
        "currency": getattr(chain, "currency", ""),
        "expiration_label": getattr(chain, "expiration_label", ""),
        "expiration_timestamp": getattr(chain, "expiration_timestamp", None),
        "underlying_price": getattr(chain, "underlying_price", None),
        "underlying_index": getattr(chain, "underlying_index", None),
        "strike_count": len(strikes),
        "atm_strike": to_jsonable(atm),
    }


def summarize_deribit_futures_curve(curve: Any) -> dict[str, Any]:
    points = list(getattr(curve, "points", ()) or ())
    return {
        "currency": getattr(curve, "currency", ""),
        "generated_timestamp_ms": getattr(curve, "generated_timestamp_ms", None),
        "point_count": len(points),
        "points": [
            {
                "instrument_name": getattr(point, "instrument_name", ""),
                "expiration_label": getattr(point, "expiration_label", None),
                "is_perpetual": getattr(point, "is_perpetual", False),
                "mid_price": getattr(point, "mid_price", None),
                "mark_price": getattr(point, "mark_price", None),
                "open_interest": getattr(point, "open_interest", None),
                "basis_vs_perpetual": getattr(point, "basis_vs_perpetual", None),
                "annualized_basis_vs_perpetual": getattr(point, "annualized_basis_vs_perpetual", None),
            }
            for point in points[:12]
        ],
        "truncated": len(points) > 12,
    }


def summarize_edgar_insider(summary: Any) -> dict[str, Any]:
    return {
        "ticker": getattr(summary, "ticker", ""),
        "company_name": getattr(summary, "company_name", ""),
        "cik": getattr(summary, "cik", ""),
        "total_form4_count": getattr(summary, "total_form4_count", 0),
        "recent_form4s": [
            to_jsonable(item) for item in list(getattr(summary, "recent_form4s", ()) or ())[:5]
        ],
    }


def summarize_yield_curve(snapshot: Any) -> dict[str, Any]:
    tenors = {point.tenor: point.value for point in getattr(snapshot, "points", ())}
    return {
        "date": getattr(snapshot, "date", ""),
        "curve_kind": getattr(snapshot, "curve_kind", ""),
        "tenors": tenors,
        "spread_10y_2y": snapshot.spread("10Y", "2Y"),
        "spread_10y_3m": snapshot.spread("10Y", "3M"),
    }


def summarize_fed_meeting(meeting: Any) -> dict[str, Any]:
    return {
        "meeting_date": getattr(meeting, "meeting_date", ""),
        "current_target_low": getattr(meeting, "current_target_low", None),
        "current_target_high": getattr(meeting, "current_target_high", None),
        "probabilities": to_jsonable(getattr(meeting, "probabilities", ())),
    }


def summarize_worldbank_result(result: Any) -> dict[str, Any]:
    points = list(getattr(result, "points", ()) or ())
    return {
        "indicator_id": getattr(result, "indicator_id", ""),
        "indicator_name": getattr(result, "indicator_name", ""),
        "point_count": len(points),
        "latest_points": [to_jsonable(point) for point in points[:16]],
        "truncated": len(points) > 16,
    }


def summarize_web_search_result(result: Any) -> dict[str, Any]:
    snippets = list(getattr(result, "snippets", ()) or ())
    return {
        "query": getattr(result, "query", ""),
        "fetched_at": getattr(result, "fetched_at", ""),
        "snippet_count": len(snippets),
        "snippets": [to_jsonable(snippet) for snippet in snippets[:8]],
        "truncated": len(snippets) > 8,
    }


def summarize_tencent_metrics(metrics: Any) -> dict[str, Any]:
    data = to_jsonable(metrics)
    keep_keys = (
        "symbol",
        "name",
        "price",
        "change_pct",
        "turnover_rate",
        "volume_ratio",
        "pe",
        "pb",
        "float_market_cap_cny_100m",
        "total_market_cap_cny_100m",
        "amount_cny_10k",
    )
    return {key: data.get(key) for key in keep_keys if key in data}


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {
            key: to_jsonable(item)
            for key, item in asdict(value).items()
            if key not in {"raw", "raw_fields", "raw_quotes"}
        }
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def compact_json(value: Any, max_chars: int) -> str:
    text = json.dumps(to_jsonable(value), ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def percent_change(start: Any, end: Any) -> float | None:
    try:
        start_float = float(start)
        end_float = float(end)
    except (TypeError, ValueError):
        return None
    if start_float == 0:
        return None
    return round((end_float / start_float - 1) * 100, 4)


def realized_volatility(closes: list[float]) -> float | None:
    if len(closes) < 3:
        return None
    returns = []
    for previous, current in zip(closes, closes[1:]):
        if previous <= 0 or current <= 0:
            continue
        returns.append(math.log(current / previous))
    if len(returns) < 2:
        return None
    mean_return = sum(returns) / len(returns)
    variance = sum((item - mean_return) ** 2 for item in returns) / (len(returns) - 1)
    return round(math.sqrt(variance) * math.sqrt(252), 6)


def safe_average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def to_yahoo_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.endswith(".US"):
        return normalized[:-3]
    return normalized


def is_plain_us_equity(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    if any(marker in normalized for marker in ("=", "^", ".", "-")):
        return False
    return bool(re.fullmatch(r"[A-Z]{1,5}", normalized))


def is_a_share_symbol(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    return bool(
        re.fullmatch(r"(SH|SZ)?\d{6}", normalized)
        or re.fullmatch(r"\d{6}\.(SH|SZ)", normalized)
    )


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


