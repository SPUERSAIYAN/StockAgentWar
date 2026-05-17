from __future__ import annotations

import math
import re
import json
import contextlib
import io
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Callable

from collectors.connectors.china import build_china_equity_tasks
from collectors.connectors.crypto import build_crypto_tasks
from collectors.connectors.equity import build_equity_tasks
from collectors.connectors.macro import build_macro_tasks
from collectors.connectors.prediction import build_prediction_market_tasks
from collectors.connectors.web_search import build_web_search_tasks
from collectors.local_a_share_concepts import discover_local_concept_board_candidates
from agents.trace_logger import (
    log_collector_summary,
    log_data_source_error,
    log_data_source_plan,
    log_data_source_start,
    log_data_source_success,
    log_trace,
)
from schemas.state import AgentRuntimeConfig, MarketDecisionState

DEFAULT_COLLECTOR_CONFIG: dict[str, Any] = {
    "enabled": True,
    "timeout_seconds": 90,
    "max_workers": 12,
    "yahoo_max_workers": 1,
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
            "edgar_filings": True,
            "edgar_filing_forms": "10-K,10-Q",
            "edgar_filing_limit": 8,
            "stooq_compat": False,
        },
        "china_equity": {
            "enabled": True,
            "tencent": True,
            "tencent_index_metrics": True,
            "tencent_index_symbols": ("sh000001", "sz399001", "sz399006"),
            "mootdx": False,
            "mootdx_frequencies": ("day",),
            "mootdx_minute_bar_offset": 240,
            "mootdx_intraday": False,
            "mootdx_order_book": False,
            "mootdx_shareholders": False,
            "mootdx_company_profile": False,
            "mootdx_index_symbols": (),
            "mootdx_index_frequencies": ("day",),
            "mootdx_local_tdxdir": "",
            "mootdx_local_frequencies": ("day",),
            "mootdx_local_market": "std",
        },
        "macro": {
            "enabled": True,
            "treasury": True,
            "treasury_curve_kinds": ("real", "bill", "long_term"),
            "treasury_exchange_rates": True,
            "treasury_exchange_rate_countries": ("China", "Japan"),
            "treasury_exchange_rate_limit": 12,
            "fear_greed": True,
            "cme_fedwatch": True,
            "cftc": True,
            "bis": False,
            "worldbank": False,
        },
        "prediction_markets": {
            "enabled": True,
            "kalshi": True,
            "kalshi_event_tickers": (),
            "kalshi_orderbook_tickers": (),
            "kalshi_orderbook_depth": 10,
            "polymarket": True,
            "polymarket_event_slugs": (),
            "polymarket_orderbook_token_ids": (),
        },
        "crypto": {
            "enabled": True,
            "coingecko": True,
            "deribit": True,
            "deribit_orderbook_instruments": (),
            "deribit_orderbook_depth": 5,
        },
        "web_search": {
            "enabled": False,
            "pages": (),
            "max_page_chars": 8000,
        },
    },
    "candidate_discovery": {
        "enabled": True,
        "max_candidates": 8,
        "scan_limit": 0,
        "batch_size": 80,
        "local_concept_board_path": "astockdate/全部A股20264.xlsx",
    },
}


def collect_market_information(
    state: MarketDecisionState,
    config: AgentRuntimeConfig,
) -> dict[str, Any] | None:
    collector_config = merge_dicts(DEFAULT_COLLECTOR_CONFIG, dict(config.get("collector", {})))
    collector_config, collection_profile = apply_a_share_collection_profile(state, collector_config)
    collector_name = config.get("name", "information")
    log_collector_summary(
        enabled=collector_config.get("enabled", False) is not False,
        timeout_seconds=collector_config.get("timeout_seconds"),
        max_workers=collector_config.get("max_workers"),
        yahoo_max_workers=collector_config.get("yahoo_max_workers"),
        providers=dict(collector_config.get("providers", {})),
    )
    log_trace(
        collector_name,
        "COLLECTOR PROFILE",
        {"a_share_collection_profile": collection_profile},
    )
    if collector_config.get("enabled", False) is False:
        log_trace(collector_name, "COLLECTOR SKIP", {"reason": "collector disabled"})
        return None

    try:
        from collectors.digital_oracle import gather
    except Exception as exc:
        log_data_source_error("digital_oracle_import", 0, exc)
        return {
            "collection_status": "unavailable",
            "generated_at": now_iso(),
            "a_share_collection_profile": collection_profile,
            "sources": {},
            "errors": {"digital_oracle_import": f"{type(exc).__name__}: {exc}"},
        }

    discovery = (
        discover_candidate_universe(state, collector_config)
        if is_provider_enabled(collector_config, "china_equity")
        else None
    )
    if discovery:
        state = {
            **state,
            "candidates": discovery["candidates"],
            "metadata": {
                **dict(state.get("metadata", {})),
                "auto_candidate_discovery": discovery,
            },
        }

    symbols = extract_candidate_symbols(state)
    if not symbols and not can_collect_without_symbols(collector_config):
        raw_summary: dict[str, Any] = {
            "collection_status": "empty",
            "generated_at": now_iso(),
            "a_share_collection_profile": collection_profile,
            "sources": {},
            "errors": {
                "symbols": (
                    "No candidate symbols were provided and automatic candidate "
                    "discovery did not match the task."
                )
            },
        }
        if discovery:
            raw_summary["candidate_discovery"] = render_candidate_discovery(discovery)
        return raw_summary

    timeout_seconds = float(collector_config.get("timeout_seconds", 35))
    max_workers = int(collector_config.get("max_workers", 12))
    yahoo_max_workers = int(collector_config.get("yahoo_max_workers", 1))

    tasks: dict[str, Callable[[], Any]] = {}
    task_build_errors: dict[str, BaseException] = {}
    a_share_symbols = [symbol for symbol in symbols if is_a_share_symbol(symbol)]
    global_symbols = [symbol for symbol in symbols if symbol not in a_share_symbols]

    add_task_group(
        tasks,
        task_build_errors,
        "task_build.us_equity",
        lambda: build_equity_tasks(
            symbols=global_symbols,
            config=collector_config,
            is_plain_us_equity=is_plain_us_equity,
            to_yahoo_symbol=to_yahoo_symbol,
        ),
    )
    add_task_group(
        tasks,
        task_build_errors,
        "task_build.china_equity",
        lambda: build_china_equity_tasks(symbols=a_share_symbols, config=collector_config),
    )
    add_task_group(
        tasks,
        task_build_errors,
        "task_build.macro",
        lambda: build_macro_tasks(config=collector_config),
    )
    add_task_group(
        tasks,
        task_build_errors,
        "task_build.prediction_markets",
        lambda: build_prediction_market_tasks(
            task=state.get("task", ""),
            symbols=symbols,
            config=collector_config,
        ),
    )
    add_task_group(
        tasks,
        task_build_errors,
        "task_build.crypto",
        lambda: build_crypto_tasks(config=collector_config),
    )
    add_task_group(
        tasks,
        task_build_errors,
        "task_build.web_search",
        lambda: build_web_search_tasks(
            task=state.get("task", ""),
            symbols=symbols,
            config=collector_config,
        ),
    )
    log_data_source_plan(
        task_count=len(tasks),
        symbols=symbols,
        tasks=sorted(tasks.keys()),
        task_build_errors={
            label: f"{type(exc).__name__}: {exc}"
            for label, exc in task_build_errors.items()
        },
    )

    traced_tasks = trace_data_source_tasks(tasks, task=state.get("task", ""), symbols=symbols)
    standard_tasks, yahoo_tasks = split_yahoo_tasks(traced_tasks)
    gathered_results: dict[str, Any] = {}
    gathered_errors: dict[str, BaseException] = {}

    if standard_tasks:
        gathered = gather(
            standard_tasks,
            max_workers=max_workers,
            timeout_seconds=timeout_seconds,
            fail_fast=False,
        )
        gathered_results.update(gathered.results)
        gathered_errors.update(gathered.errors)

    if yahoo_tasks:
        yahoo_results, yahoo_errors = gather_yahoo_tasks(
            yahoo_tasks,
            gather=gather,
            max_workers=yahoo_max_workers,
            timeout_seconds=timeout_seconds,
        )
        gathered_results.update(yahoo_results)
        gathered_errors.update(yahoo_errors)

    for label, exc in gathered_errors.items():
        if isinstance(exc, TimeoutError):
            log_data_source_error(label, int(timeout_seconds * 1000), exc)
    return summarize_gathered_market_data(
        task=state.get("task", ""),
        symbols=symbols,
        results=gathered_results,
        errors={**task_build_errors, **gathered_errors},
        discovery=discovery,
        collection_profile=collection_profile,
    )


def gather_yahoo_tasks(
    tasks: dict[str, Callable[[], Any]],
    *,
    gather: Callable[..., Any],
    max_workers: int,
    timeout_seconds: float,
) -> tuple[dict[str, Any], dict[str, BaseException]]:
    if max_workers > 1:
        gathered = gather(
            tasks,
            max_workers=max_workers,
            timeout_seconds=timeout_seconds,
            fail_fast=False,
        )
        return gathered.results, gathered.errors

    results: dict[str, Any] = {}
    errors: dict[str, BaseException] = {}
    for label, fn in tasks.items():
        gathered = gather(
            {label: fn},
            max_workers=1,
            timeout_seconds=timeout_seconds,
            fail_fast=False,
        )
        results.update(gathered.results)
        errors.update(gathered.errors)
    return results, errors


def split_yahoo_tasks(
    tasks: dict[str, Callable[[], Any]],
) -> tuple[dict[str, Callable[[], Any]], dict[str, Callable[[], Any]]]:
    standard_tasks: dict[str, Callable[[], Any]] = {}
    yahoo_tasks: dict[str, Callable[[], Any]] = {}
    for label, fn in tasks.items():
        if is_yahoo_backed_task(label):
            yahoo_tasks[label] = fn
        else:
            standard_tasks[label] = fn
    return standard_tasks, yahoo_tasks


def is_yahoo_backed_task(label: str) -> bool:
    if label.startswith("macro.price."):
        return True
    if not label.startswith("equity."):
        return False
    data_kind = label.split(".")[-1]
    return data_kind in {
        "price_daily",
        "price_weekly",
        "stooq_price_daily",
        "options_nearest",
    }


def trace_data_source_tasks(
    tasks: dict[str, Callable[[], Any]],
    *,
    task: str,
    symbols: list[str],
) -> dict[str, Callable[[], Any]]:
    return {
        label: trace_data_source_task(label, fn, task=task, symbols=symbols)
        for label, fn in tasks.items()
    }


def add_task_group(
    tasks: dict[str, Callable[[], Any]],
    errors: dict[str, BaseException],
    label: str,
    build: Callable[[], dict[str, Callable[[], Any]]],
) -> None:
    log_data_source_start(label)
    started_at = time.perf_counter()
    try:
        built_tasks = build()
    except Exception as exc:
        errors[label] = exc
        log_data_source_error(label, elapsed_since(started_at), exc)
        return
    tasks.update(built_tasks)
    log_data_source_success(
        label,
        elapsed_since(started_at),
        {
            "task_count": len(built_tasks),
            "tasks": sorted(built_tasks.keys()),
        },
    )


def trace_data_source_task(
    label: str,
    fn: Callable[[], Any],
    *,
    task: str,
    symbols: list[str],
) -> Callable[[], Any]:
    def wrapped() -> Any:
        context = infer_data_source_context(label, task=task, symbols=symbols)
        log_data_source_start(label, context)
        started_at = time.perf_counter()
        try:
            value = fn()
        except Exception as exc:
            log_data_source_error(label, elapsed_since(started_at), exc)
            raise
        log_data_source_success(label, elapsed_since(started_at), value)
        return value

    return wrapped


def infer_data_source_context(label: str, *, task: str, symbols: list[str]) -> dict[str, Any]:
    parts = label.split(".")
    context: dict[str, Any] = {
        "label": label,
        "task": task,
        "all_symbols": symbols,
    }
    if label.startswith("equity.") and len(parts) >= 3:
        context.update(
            {
                "group": "equity",
                "symbol": parts[1],
                "data_kind": ".".join(parts[2:]),
            }
        )
    elif label.startswith("macro.price."):
        context.update(
            {
                "group": "macro",
                "symbol": label.removeprefix("macro.price."),
                "data_kind": "price_history",
            }
        )
    elif label.startswith("macro."):
        context.update({"group": "macro", "data_kind": label.removeprefix("macro.")})
    elif label.startswith("prediction."):
        context.update({"group": "prediction_markets", "data_kind": label.removeprefix("prediction.")})
    elif label.startswith("crypto."):
        context.update({"group": "crypto", "data_kind": label.removeprefix("crypto.")})
    elif label.startswith("web.search."):
        context.update({"group": "web_search", "data_kind": "search"})
    elif label.startswith("web.page."):
        context.update({"group": "web_search", "data_kind": "page_fetch"})
    elif label.startswith("china."):
        context.update({"group": "china_equity", "data_kind": label.removeprefix("china.")})
    return context


def elapsed_since(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def is_provider_enabled(config: dict[str, Any], group: str) -> bool:
    provider_config = dict(config.get("providers", {}).get(group, {}) or {})
    return provider_config.get("enabled", True) is not False


def apply_a_share_collection_profile(
    state: MarketDecisionState,
    config: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    profile = resolve_a_share_collection_profile(state)
    if profile != "sector_shallow":
        return config, profile

    overrides = {
        "include_macro": False,
        "candidate_discovery": {
            "max_candidates": 60,
        },
        "providers": {
            "macro": {
                "enabled": False,
            },
            "china_equity": {
                "tencent_index_metrics": True,
                "mootdx_frequencies": ("day",),
                "mootdx_realtime": False,
                "mootdx_intraday": False,
                "mootdx_order_book": False,
                "mootdx_financials": True,
                "mootdx_shareholders": False,
                "mootdx_company_profile": False,
                "mootdx_transactions": False,
                "mootdx_index_frequencies": ("day",),
            },
        },
    }
    return merge_dicts(config, overrides), profile


def resolve_a_share_collection_profile(state: MarketDecisionState) -> str:
    explicit_a_share_symbols = [
        symbol for symbol in extract_candidate_symbols(state) if is_a_share_symbol(symbol)
    ]
    if explicit_a_share_symbols:
        return "stock_deep"

    metadata = dict(state.get("metadata", {}) or {})
    mode = str(metadata.get("mode") or metadata.get("ui_mode") or "")
    if mode == "a_share_sector" or extract_requested_sectors(state):
        return "sector_shallow"

    return "default"


def can_collect_without_symbols(config: dict[str, Any]) -> bool:
    return any(
        is_provider_enabled(config, group)
        for group in ("macro", "prediction_markets", "crypto", "web_search")
    ) or can_collect_china_without_symbols(config)


def can_collect_china_without_symbols(config: dict[str, Any]) -> bool:
    provider_config = dict(config.get("providers", {}).get("china_equity", {}) or {})
    if provider_config.get("enabled", True) is False:
        return False

    include_tencent = bool(provider_config.get("tencent", config.get("include_a_share_metrics", True)))
    if include_tencent and bool(provider_config.get("tencent_index_metrics", True)):
        return True

    include_mootdx = bool(provider_config.get("mootdx", False))
    index_symbols = tuple(provider_config.get("mootdx_index_symbols", ()))
    return include_mootdx and bool(index_symbols)


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


def discover_candidate_universe(
    state: MarketDecisionState,
    config: AgentRuntimeConfig,
) -> dict[str, Any] | None:
    if extract_candidate_symbols(state):
        return None

    discovery_config = dict(config.get("candidate_discovery", {}))
    if discovery_config.get("enabled", True) is False:
        return None

    requested_sectors = extract_requested_sectors(state)
    if requested_sectors:
        discovery = discover_local_concept_board_candidates(
            requested_sectors,
            discovery_config,
        )
        candidates = discovery.pop("candidates")
        return {
            "mode": "provider_sector_discovery",
            "universe": "china_a_share_sector",
            "method": discovery.pop("method"),
            "reason": (
                "A 股指定概念板块候选来自本地 Excel 概念板块表；"
                "后续行情和估值字段继续使用已启用的 A 股行情源补充。"
            ),
            "candidates": candidates,
            **discovery,
        }

    universe_name = infer_auto_candidate_universe(state.get("task", ""))
    if not universe_name:
        return None

    discovery = discover_dynamic_candidates(
        universe_name=universe_name,
        config=config,
        discovery_config=discovery_config,
    )
    if not discovery:
        return None

    candidates = discovery.pop("candidates")
    return {
        "mode": "provider_candidate_discovery",
        "universe": universe_name,
        "method": discovery.pop("method"),
        "reason": build_discovery_reason(universe_name),
        "candidates": candidates,
        **discovery,
    }


def extract_requested_sectors(state: MarketDecisionState) -> list[str]:
    scan_scope = dict(state.get("scan_scope", {}) or {})
    sectors = scan_scope.get("sectors") or []
    if isinstance(sectors, list):
        normalized = [str(item).strip() for item in sectors if str(item).strip()]
        if normalized:
            return normalized

    question_understanding = dict(state.get("question_understanding", {}) or {})
    sector_terms = question_understanding.get("sector_terms") or []
    if isinstance(sector_terms, str):
        sector_terms = re.split(r"[,，、]", sector_terms)
    normalized_terms = (
        [str(item).strip() for item in sector_terms if str(item).strip()]
        if isinstance(sector_terms, list)
        else []
    )
    if normalized_terms:
        return normalized_terms

    actions = state.get("data_collection_actions", []) or []
    action_terms: list[str] = []
    if isinstance(actions, list):
        for item in actions:
            if not isinstance(item, dict):
                continue
            if str(item.get("action") or "").upper() != "CALL_LOCAL_CONCEPT_BOARD":
                continue
            raw_terms = item.get("input_terms") or []
            if isinstance(raw_terms, str):
                raw_terms = re.split(r"[,，、]", raw_terms)
            if isinstance(raw_terms, list):
                for term in raw_terms:
                    text = str(term).strip()
                    if text and text not in action_terms:
                        action_terms.append(text)
    return action_terms


def infer_auto_candidate_universe(task: str) -> str | None:
    normalized = task.casefold()
    china_tokens = (
        "a-share",
        "ashare",
        "china",
        "chinese stock",
        "\u5927a",
        "\u5927 a",
        "a\u80a1",
        "\u6caa\u6df1",
        "\u4e2d\u56fd\u80a1",
        "\u4e2d\u56fd\u80a1\u7968",
    )
    stock_selection_tokens = (
        "\u80a1",
        "\u80a1\u7968",
        "\u54ea\u4e00\u53ea",
        "\u54ea\u53ea",
        "\u5019\u9009",
        "\u6700\u6709\u6f5c\u529b",
        "\u7b5b\u9009",
    )
    potential_tokens = ("\u672a\u6765", "\u6f5c\u529b")
    if any(token in normalized for token in china_tokens):
        return "china_a_share_core"
    if any(token in normalized for token in stock_selection_tokens) and any(
        token in normalized for token in potential_tokens
    ):
        return "china_a_share_core"
    return None


def build_discovery_reason(universe_name: str) -> str:
    if universe_name == "china_a_share_core":
        return (
            "The task asks for stock selection without explicit symbols. "
            "Candidates were discovered at runtime from the A-share stock list "
            "and ranked by live Tencent trading and valuation metrics before "
            "deeper provider collection."
        )
    return "Generated an automatic candidate universe for the task."


def discover_dynamic_candidates(
    *,
    universe_name: str,
    config: AgentRuntimeConfig,
    discovery_config: dict[str, Any],
) -> dict[str, Any] | None:
    if universe_name != "china_a_share_core":
        return None
    return discover_china_a_share_candidates(config, discovery_config)


def discover_china_a_share_candidates(
    config: AgentRuntimeConfig,
    discovery_config: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        from collectors.digital_oracle import MootdxProvider, TencentFinanceProvider
    except Exception as exc:
        log_data_source_error("candidate_discovery.digital_oracle_import", 0, exc)
        return None

    provider_config = dict(config.get("providers", {}).get("china_equity", {}))
    factory_options = dict(provider_config.get("mootdx_factory_options", {}))
    max_candidates = int(discovery_config.get("max_candidates", 8))
    scan_limit = int(discovery_config.get("scan_limit", 0))
    batch_size = max(int(discovery_config.get("batch_size", 80)), 1)
    a_share_filters = dict(discovery_config.get("a_share_filters", {}) or {})

    try:
        log_data_source_start(
            "candidate_discovery.mootdx_stock_list",
            {
                "universe": "china_a_share_core",
                "scan_limit": scan_limit,
                "factory_options": factory_options,
            },
        )
        started_at = time.perf_counter()
        mootdx = MootdxProvider(**factory_options)
        stock_rows = list_mootdx_a_share_symbols(mootdx)
        log_data_source_success(
            "candidate_discovery.mootdx_stock_list",
            elapsed_since(started_at),
            {
                "row_count": len(stock_rows),
                "preview": stock_rows[:8],
            },
        )
        if scan_limit > 0:
            stock_rows = stock_rows[:scan_limit]
        symbols = [row["symbol"] for row in stock_rows]
        tencent = TencentFinanceProvider()
        log_data_source_start(
            "candidate_discovery.tencent_metrics",
            {
                "symbol_count": len(symbols),
                "batch_size": batch_size,
            },
        )
        started_at = time.perf_counter()
        metrics = fetch_tencent_metrics_for_symbols(tencent, symbols, batch_size=batch_size)
        log_data_source_success(
            "candidate_discovery.tencent_metrics",
            elapsed_since(started_at),
            {
                "metric_count": len(metrics),
                "preview": metrics[:3],
            },
        )
    except Exception as exc:
        log_data_source_error("candidate_discovery", 0, exc)
        return None

    ranked: list[dict[str, Any]] = []
    filtered_out_count = 0
    names_by_symbol = {row["symbol"]: row.get("name", "") for row in stock_rows}
    for metric in metrics:
        item = to_jsonable(metric)
        symbol = tencent_symbol_to_a_share_symbol(str(item.get("symbol", "")))
        if not symbol:
            continue
        if not passes_a_share_candidate_filters(item, a_share_filters):
            filtered_out_count += 1
            continue
        score, basis = score_discovered_a_share(item)
        ranked.append(
            {
                "symbol": symbol,
                "name": item.get("name") or names_by_symbol.get(symbol, ""),
                "market": "CN",
                "reason": basis,
                "score": score,
                "metadata": {
                    key: item.get(key)
                    for key in (
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
                    if key in item
                },
            }
        )

    ranked = [
        row
        for row in sorted(ranked, key=lambda item: item.get("score", 0), reverse=True)
        if row.get("score") is not None
    ]
    if not ranked:
        return None
    return {
        "method": "mootdx_stock_list_plus_tencent_metrics",
        "scanned_symbol_count": len(symbols),
        "ranked_symbol_count": len(ranked),
        "filtered_out_count": filtered_out_count,
        "a_share_filters": a_share_filters,
        "candidates": ranked[:max_candidates],
    }


def passes_a_share_candidate_filters(
    metrics: dict[str, Any],
    filters: dict[str, Any],
) -> bool:
    if not filters:
        return True

    name = str(metrics.get("name") or "").upper()
    if filters.get("exclude_st", True) and "ST" in name:
        return False

    price = to_float(metrics.get("price"))
    if filters.get("exclude_suspended", True) and (price is None or price <= 0):
        return False

    min_market_cap = to_float(filters.get("min_market_cap_yi"))
    market_cap = to_float(metrics.get("total_market_cap_cny_100m"))
    if min_market_cap is not None and market_cap is not None and market_cap < min_market_cap:
        return False

    max_pe = to_float(filters.get("max_pe"))
    pe = to_float(metrics.get("pe"))
    if max_pe is not None and pe is not None and pe > 0 and pe > max_pe:
        return False

    return True


def list_mootdx_a_share_symbols(mootdx: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for market, suffix, prefixes in (
        ("sh", ".SH", ("600", "601", "603", "605", "688")),
        ("sz", ".SZ", ("000", "001", "002", "003", "300", "301")),
    ):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            stocks = mootdx.list_stocks(market)
        for stock in stocks:
            code = str(getattr(stock, "symbol", "")).strip()
            name = str(getattr(stock, "name", "") or "").replace("\x00", "").strip()
            if not code.startswith(prefixes):
                continue
            if not re.fullmatch(r"\d{6}", code):
                continue
            if "ST" in name.upper():
                continue
            rows.append({"symbol": f"{code}{suffix}", "name": name})
    return rows


def fetch_tencent_metrics_for_symbols(
    tencent: Any,
    symbols: list[str],
    *,
    batch_size: int,
) -> list[Any]:
    from collectors.digital_oracle import TencentStockMetricsQuery

    metrics: list[Any] = []
    for start in range(0, len(symbols), batch_size):
        batch = tuple(symbols[start : start + batch_size])
        if not batch:
            continue
        label = f"candidate_discovery.tencent_metrics.batch_{start // batch_size + 1}"
        log_data_source_start(
            label,
            {
                "batch_start": start,
                "batch_size": len(batch),
                "symbols_preview": batch[:8],
            },
        )
        started_at = time.perf_counter()
        try:
            batch_metrics = tencent.get_stock_metrics(TencentStockMetricsQuery(symbols=batch))
            metrics.extend(batch_metrics)
            log_data_source_success(
                label,
                elapsed_since(started_at),
                {
                    "metric_count": len(batch_metrics),
                    "preview": batch_metrics[:3],
                },
            )
        except Exception as exc:
            log_data_source_error(label, elapsed_since(started_at), exc)
            continue
    return metrics


def tencent_symbol_to_a_share_symbol(symbol: str) -> str | None:
    normalized = symbol.strip().lower()
    if re.fullmatch(r"sh\d{6}", normalized):
        return f"{normalized[2:].upper()}.SH"
    if re.fullmatch(r"sz\d{6}", normalized):
        return f"{normalized[2:].upper()}.SZ"
    if re.fullmatch(r"bj\d{6}", normalized):
        return f"{normalized[2:].upper()}.BJ"
    return None


def score_discovered_a_share(metrics: dict[str, Any]) -> tuple[float, str]:
    score = 0.0
    basis: list[str] = []

    change_pct = to_float(metrics.get("change_pct"))
    if change_pct is not None:
        score += max(min(change_pct / 3.0, 2.0), -2.0)
        basis.append(f"daily change {change_pct}%")

    volume_ratio = to_float(metrics.get("volume_ratio"))
    if volume_ratio is not None:
        score += max(min((volume_ratio - 1.0) * 1.5, 1.5), -1.0)
        basis.append(f"volume ratio {volume_ratio}")

    turnover_rate = to_float(metrics.get("turnover_rate"))
    if turnover_rate is not None:
        score += max(min(turnover_rate / 4.0, 1.2), 0.0)
        basis.append(f"turnover {turnover_rate}%")

    amount = to_float(metrics.get("amount_cny_10k"))
    if amount is not None and amount > 0:
        score += min(math.log10(amount) / 3.0, 2.0)
        basis.append("liquidity present")

    pe = to_float(metrics.get("pe"))
    if pe is not None and pe > 0:
        if pe <= 60:
            score += 1.0
            basis.append(f"PE {pe} within growth range")
        elif pe > 100:
            score -= 1.0
            basis.append(f"PE {pe} is demanding")

    pb = to_float(metrics.get("pb"))
    if pb is not None and pb > 0:
        if pb <= 8:
            score += 0.5
            basis.append(f"PB {pb} below high-premium zone")
        elif pb > 15:
            score -= 0.5
            basis.append(f"PB {pb} is elevated")

    market_cap = to_float(metrics.get("total_market_cap_cny_100m"))
    if market_cap is not None and market_cap > 0:
        score += min(math.log10(market_cap) / 4.0, 1.2)
        basis.append("large tradable market-cap anchor")

    return round(score, 3), "; ".join(basis) or "live Tencent metrics available"


def summarize_gathered_market_data(
    *,
    task: str,
    symbols: list[str],
    results: dict[str, Any],
    errors: dict[str, BaseException],
    discovery: dict[str, Any] | None = None,
    collection_profile: str = "default",
) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    discovery_source_values = dict(discovery.get("sources", {}) if discovery else {})
    for label, value in discovery_source_values.items():
        sources[label] = summarize_provider_value(value)
    for label, value in results.items():
        sources[label] = summarize_provider_value(value)

    discovery_errors = dict(discovery.get("errors", {}) if discovery else {})
    rendered_errors = {
        label: f"{type(exc).__name__}: {exc}"
        for label, exc in {**discovery_errors, **errors}.items()
    }
    if sources and rendered_errors:
        status = "partial"
    elif sources:
        status = "ok"
    else:
        status = "failed"

    summary = {
        "collection_status": status,
        "generated_at": now_iso(),
        "a_share_collection_profile": collection_profile,
        "task": task,
        "symbols": symbols,
        "source_count": len(sources),
        "error_count": len(rendered_errors),
        "sources": sources,
        "errors": rendered_errors,
    }
    if discovery:
        summary["candidate_discovery"] = render_candidate_discovery(discovery)
    return summary


def render_candidate_discovery(discovery: dict[str, Any]) -> dict[str, Any]:
    rendered = dict(discovery)
    sources = dict(rendered.pop("sources", {}) or {})
    errors = dict(rendered.pop("errors", {}) or {})
    if sources:
        rendered["source_labels"] = sorted(sources.keys())
    if errors:
        rendered["errors"] = {
            label: f"{type(exc).__name__}: {exc}" for label, exc in errors.items()
        }
    return rendered


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
    if class_name == "WebPageContent":
        return summarize_web_page_content(value)
    if class_name == "MootdxCompanyProfile":
        return summarize_mootdx_company_profile(value)
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


def summarize_web_page_content(page: Any, *, max_chars: int = 1200) -> dict[str, Any]:
    text = str(getattr(page, "text", "") or "")
    return {
        "url": getattr(page, "url", ""),
        "title": getattr(page, "title", ""),
        "fetched_at": getattr(page, "fetched_at", ""),
        "text": text[:max_chars],
        "truncated": bool(getattr(page, "truncated", False)) or len(text) > max_chars,
    }


def summarize_mootdx_company_profile(profile: Any, *, max_chars: int = 1200) -> dict[str, Any]:
    sections = dict(getattr(profile, "sections", {}) or {})
    rendered: dict[str, str] = {}
    for name, text in list(sections.items())[:6]:
        text_value = str(text or "")
        rendered[str(name)] = text_value[:max_chars]
    return {
        "symbol": getattr(profile, "symbol", ""),
        "section_count": len(sections),
        "sections": rendered,
        "truncated": any(len(str(text or "")) > max_chars for text in sections.values()) or len(sections) > 6,
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


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        re.fullmatch(r"(SH|SZ|BJ)?\d{6}", normalized)
        or re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", normalized)
    )


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


