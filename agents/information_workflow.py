from __future__ import annotations

import re
from typing import Any

from schemas.state import AgentRuntimeConfig, MarketDecisionState


WORKFLOW_STEPS = [
    "Step 1: Understand the question",
    "Step 2: Select signals",
    "Step 3: Signal routing",
    "Step 4: Fetch data with Python providers",
    "Step 5: Analyze trading-data signals",
    "Step 6: Output structured report",
]

ROUTING_CRITERIA = ["relevance", "time_match", "information_increment"]
PROVIDER_GROUPS = (
    "us_equity",
    "china_equity",
    "macro",
    "prediction_markets",
    "crypto",
    "web_search",
)
PROVIDER_GROUP_SET = set(PROVIDER_GROUPS)


def signal(signal_id: str, provider_group: str, horizon: str, description: str) -> dict[str, Any]:
    return {
        "id": signal_id,
        "provider_group": provider_group,
        "time_horizon": horizon,
        "description": description,
    }

SIGNAL_MENU: dict[str, list[dict[str, Any]]] = {
    "geopolitical_conflict_or_war_risk": [
        signal("prediction.polymarket", "prediction_markets", "short_term", "Event-market contracts for conflict probabilities."),
        signal("prediction.kalshi", "prediction_markets", "short_term", "Regulated binary contracts for related geopolitical events."),
        signal("macro.safe_havens", "macro", "short_term", "Gold, silver and safe-haven currency price behavior."),
        signal("macro.conflict_proxies", "macro", "short_term", "Crude oil, natural gas, wheat, defense ETF and defense-stock proxies."),
        signal("macro.cftc_positioning", "macro", "medium_term", "Institutional futures positioning in commodities and risk assets."),
        signal("web.structured_gaps", "web_search", "short_term", "MOVE, CDS, BDI, war-risk premiums and OAS when structured providers lack them."),
    ],
    "economic_recession_or_macro_cycle": [
        signal("macro.yield_curve", "macro", "medium_term", "Treasury curve shape, especially 10Y-2Y and 10Y-3M spreads."),
        signal("macro.risk_assets", "macro", "short_term", "SPY, QQQ, copper, crude oil, VIX, gold and USDCNY price proxies."),
        signal("macro.cftc_positioning", "macro", "medium_term", "Managed-money positioning in copper, crude oil, gold and S&P 500."),
        signal("macro.fear_greed", "macro", "short_term", "Composite price-based risk appetite."),
        signal("macro.fedwatch", "macro", "short_term", "Futures-implied policy-rate path."),
        signal("prediction.recession", "prediction_markets", "short_term", "Prediction-market recession and policy contracts."),
        signal("crypto.risk_appetite", "crypto", "short_term", "BTC/ETH spot and derivatives as risk-appetite proxies."),
        signal("web.credit_stress", "web_search", "short_term", "High-yield OAS, MOVE, TED spread, BDI and related structured gaps."),
    ],
    "industry_cycle_or_bubble_assessment": [
        signal("equity.leader_prices", "us_equity", "short_term", "Industry leader and sector ETF price trends."),
        signal("equity.insider_activity", "us_equity", "medium_term", "EDGAR Form 4 insider-transaction cadence."),
        signal("macro.upstream_proxies", "macro", "medium_term", "Commodity, equipment-maker or sector-specific price proxies."),
        signal("crypto.industry_proxy", "crypto", "short_term", "Crypto spot and derivatives when the industry is crypto-related."),
        signal("web.structured_industry_data", "web_search", "medium_term", "Structured industry market data not covered by providers."),
    ],
    "asset_pricing_or_stock_selection": [
        signal("equity.price_trend", "us_equity", "short_term", "Daily, weekly and monthly target-asset price trend."),
        signal("equity.options", "us_equity", "short_term", "Options IV, put/call, max pain, Greeks and implied move."),
        signal("equity.insider_activity", "us_equity", "medium_term", "EDGAR Form 4 insider activity."),
        signal("macro.risk_free_anchor", "macro", "medium_term", "Treasury yields as valuation anchor."),
        signal("prediction.related_events", "prediction_markets", "short_term", "Event-market probabilities related to the asset thesis."),
        signal("crypto.asset_or_risk_proxy", "crypto", "short_term", "Crypto market data when the target asset is crypto or risk appetite matters."),
    ],
    "stock_options_or_crash_probability": [
        signal("equity.options", "us_equity", "short_term", "ATM IV, skew, put/call, max pain and implied move."),
        signal("equity.realized_volatility", "us_equity", "short_term", "Underlying realized volatility from historical prices."),
        signal("prediction.index_ranges", "prediction_markets", "short_term", "SPY/NASDAQ range markets where available."),
        signal("macro.defensive_rotation", "macro", "short_term", "Cyclical, defensive, utilities, VIX and Treasury signals."),
        signal("macro.cftc_positioning", "macro", "medium_term", "S&P 500 and VIX futures positioning."),
        signal("web.leverage_stress", "web_search", "short_term", "Margin debt, MOVE, OAS and leveraged ETF concentration when needed."),
    ],
    "china_a_share_analysis": [
        signal("china.candidate_discovery", "china_equity", "short_term", "Local Excel concept-board membership for requested A-share sectors; otherwise MooTDX stock-list scan plus Tencent realtime trading and valuation metrics."),
        signal("china.realtime_metrics", "china_equity", "short_term", "Tencent realtime price, PE, PB, market cap, turnover and volume ratio."),
        signal("china.kline_and_intraday", "china_equity", "short_term", "Mootdx bars, realtime quotes, intraday points, transactions and order book when enabled."),
        signal("china.fundamentals", "china_equity", "medium_term", "Mootdx EPS, financial summary, share capital, shareholders and F10 profile."),
        signal("macro.china_risk_pricing", "macro", "short_term", "FXI/KWEB/ASHR, USDCNY, VIX and global risk proxies."),
        signal("macro.credit_cycle", "macro", "medium_term", "Rates, yield curve, BIS or World Bank macro backdrop when enabled."),
        signal("web.structured_sector_gaps", "web_search", "medium_term", "Only sector-specific structured market data gaps; no news or analyst opinions."),
    ],
}


def prepare_information_state(
    state: MarketDecisionState,
    config: AgentRuntimeConfig,
) -> tuple[MarketDecisionState, dict[str, Any] | None]:
    del config
    return state, None


def build_information_workflow(state: MarketDecisionState) -> dict[str, Any]:
    task = state.get("task", "")
    symbols = [str(item.get("symbol", "")).upper() for item in state.get("candidates", []) if item.get("symbol")]
    discovery = dict(state.get("metadata", {}).get("auto_candidate_discovery", {}) or {})
    question_understanding = dict(state.get("question_understanding", {}) or {})
    provider_selection = require_state_provider_selection(state)
    selected_groups = set(provider_selection["selected_groups"])
    question_type = infer_question_type_from_understanding(task, symbols, question_understanding)
    time_window = infer_time_window_from_understanding(task, question_understanding)
    selected_signals = select_signal_specs(question_type, task, symbols)
    selected_signals = filter_signals_to_provider_groups(selected_signals, selected_groups)
    routed_signals = route_signal_specs(selected_signals, question_type, time_window, task)
    return {
        "instruction_file": "prompts/information_agent.md",
        "workflow_steps": WORKFLOW_STEPS,
        "question_understanding": question_understanding,
        "question_decomposition": {
            "core_variable": infer_core_variable(task, symbols),
            "time_window": time_window,
            "priceability": "high" if symbols else "medium",
            "question_type": question_type,
            "candidates": symbols,
            "candidate_source": "auto_discovery" if discovery else "user_input",
            "candidate_discovery": discovery,
        },
        "signal_selection": {
            "minimum_independent_dimensions": 3,
            "selected_signals": selected_signals,
        },
        "signal_routing": {
            "criteria": ROUTING_CRITERIA,
            "routed_signals": routed_signals,
        },
        "routing_criteria": ROUTING_CRITERIA,
    }


def infer_core_variable(task: str, symbols: list[str]) -> str:
    if symbols:
        return f"Candidate stock/asset decision for {', '.join(symbols)}"
    return task.strip() or "Candidate stock decision"


def infer_time_window(task: str) -> str:
    lowered = task.lower()
    if any(token in lowered for token in ("明天", "tomorrow", "1-5", "next few days", "几天", "短线")):
        return "very_short_term_1_to_5_trading_days"
    if any(token in lowered for token in ("3-5", "5 year", "5 years", "long-term", "长期", "五年")):
        return "long_term_3_to_5_years"
    if any(token in lowered for token in ("1-3", "1 year", "3 year", "medium-term", "中期", "一年", "三年")):
        return "medium_term_1_to_3_years"
    if any(token in lowered for token in ("month", "quarter", "3 months", "短期", "月", "季度")):
        return "short_term_3_to_12_months"
    return "short_to_medium_term"


def infer_question_type(task: str, symbols: list[str]) -> str:
    lowered = task.lower()
    if any(is_a_share_symbol_text(symbol) for symbol in symbols) or any(
        token in lowered for token in ("大a", "a股", "沪深", "中国股票", "china a-share", "a-share")
    ):
        return "china_a_share_analysis"
    if any(token in lowered for token in ("明天", "哪只股票", "哪一只", "买哪只")) and not symbols:
        return "china_a_share_analysis"
    if any(token in lowered for token in ("war", "conflict", "ceasefire", "invasion", "战争", "冲突", "台海")):
        return "geopolitical_conflict_or_war_risk"
    if any(token in lowered for token in ("recession", "macro", "fed", "rate", "衰退", "宏观", "利率")):
        return "economic_recession_or_macro_cycle"
    if any(token in lowered for token in ("crash", "options", "option", "崩盘", "期权")):
        return "stock_options_or_crash_probability"
    if any(token in lowered for token in ("bubble", "industry", "sector", "泡沫", "行业")):
        return "industry_cycle_or_bubble_assessment"
    return "asset_pricing_or_stock_selection"


def infer_question_type_from_understanding(
    task: str,
    symbols: list[str],
    question_understanding: dict[str, Any],
) -> str:
    scope = str(question_understanding.get("market_scope") or "").lower()
    rewritten = str(question_understanding.get("rewritten_question") or "").lower()
    if any(token in scope or token in rewritten for token in ("a-share", "ashare", "a股", "china a-share")):
        return "china_a_share_analysis"
    return infer_question_type(task, symbols)


def infer_time_window_from_understanding(task: str, question_understanding: dict[str, Any]) -> str:
    window_text = str(question_understanding.get("time_window") or "").lower()
    if not window_text:
        return infer_time_window(task)
    if any(token in window_text for token in ("1-5", "trading day", "tomorrow", "明天", "交易日")):
        return "very_short_term_1_to_5_trading_days"
    return infer_time_window(window_text)


def filter_signals_to_provider_groups(
    selected_signals: list[dict[str, Any]],
    selected_groups: set[str],
) -> list[dict[str, Any]]:
    filtered = [dict(item) for item in selected_signals if item.get("provider_group") in selected_groups]
    existing_groups = {item["provider_group"] for item in filtered}
    for group in PROVIDER_GROUPS:
        if group not in selected_groups or group in existing_groups:
            continue
        filtered.append(
            signal(
                f"{group}.planner_selected",
                group,
                "short_term",
                "Provider group selected by QuestionPlanningAgent.",
            )
        )
        existing_groups.add(group)
    return filtered


def select_signal_specs(
    question_type: str,
    task: str,
    symbols: list[str],
) -> list[dict[str, Any]]:
    del task, symbols
    selected = [dict(item) for item in SIGNAL_MENU.get(question_type, SIGNAL_MENU["asset_pricing_or_stock_selection"])]
    provider_groups = {item["provider_group"] for item in selected}
    if len(provider_groups) >= 3:
        return selected

    for fallback in SIGNAL_MENU["economic_recession_or_macro_cycle"]:
        if fallback["provider_group"] not in provider_groups:
            selected.append(dict(fallback))
            provider_groups.add(fallback["provider_group"])
        if len(provider_groups) >= 3:
            break
    return selected


def route_signal_specs(
    selected_signals: list[dict[str, Any]],
    question_type: str,
    time_window: str,
    task: str,
) -> list[dict[str, Any]]:
    routed = []
    seen_groups: set[str] = set()
    for item in selected_signals:
        relevance = is_signal_relevant(item, question_type, task)
        time_match = is_time_match(item, time_window)
        information_increment = item["provider_group"] not in seen_groups or item["id"].startswith(("china.", "macro."))
        keep = relevance and time_match and information_increment
        if keep:
            seen_groups.add(item["provider_group"])
        routed.append(
            {
                **item,
                "criteria": {
                    "relevance": relevance,
                    "time_match": time_match,
                    "information_increment": information_increment,
                },
                "decision": "keep" if keep else "reject",
            }
        )

    if sum(1 for item in routed if item["decision"] == "keep") < 3:
        for item in routed:
            if item["decision"] == "reject" and item["criteria"]["relevance"]:
                item["decision"] = "keep"
            if sum(1 for candidate in routed if candidate["decision"] == "keep") >= 3:
                break
    return routed


def is_signal_relevant(signal_spec: dict[str, Any], question_type: str, task: str) -> bool:
    group = signal_spec["provider_group"]
    lowered = task.lower()
    if group == "crypto":
        return question_type in {"economic_recession_or_macro_cycle", "industry_cycle_or_bubble_assessment"} or any(
            token in lowered for token in ("crypto", "bitcoin", "btc", "eth", "加密")
        )
    if group == "web_search":
        return should_enable_web_search(task, {}) or any(
            token in lowered for token in ("sector", "industry", "板块", "行业")
        )
    return True


def is_time_match(signal_spec: dict[str, Any], time_window: str) -> bool:
    horizon = signal_spec["time_horizon"]
    if time_window == "short_term_3_to_12_months":
        return horizon in {"short_term", "medium_term"}
    if time_window == "medium_term_1_to_3_years":
        return horizon in {"short_term", "medium_term", "long_term"}
    if time_window == "long_term_3_to_5_years":
        return horizon in {"medium_term", "long_term"}
    return True


def select_information_providers(
    state: MarketDecisionState,
    workflow: dict[str, Any],
    config: AgentRuntimeConfig,
) -> dict[str, Any]:
    del config
    provider_selection = require_state_provider_selection(state)
    basis = {
        **dict(provider_selection.get("basis", {}) or {}),
        "question_type": workflow["question_decomposition"]["question_type"],
        "time_window": workflow["question_decomposition"]["time_window"],
    }
    return {
        **provider_selection,
        "basis": basis,
    }


def require_state_provider_selection(state: MarketDecisionState) -> dict[str, Any]:
    provider_selection = state.get("provider_selection")
    if not isinstance(provider_selection, dict):
        raise ValueError("Information analysis requires provider_selection from QuestionPlanningAgent.")

    selected_groups = provider_selection.get("selected_groups")
    if not isinstance(selected_groups, list):
        raise ValueError("provider_selection.selected_groups must be a list.")
    selected = []
    for group in selected_groups:
        group_text = str(group).strip()
        if group_text not in PROVIDER_GROUP_SET:
            raise ValueError(f"Unknown provider group: {group_text}")
        if group_text not in selected:
            selected.append(group_text)
    if not selected:
        raise ValueError("provider_selection.selected_groups must not be empty.")

    raw_providers = provider_selection.get("providers")
    if not isinstance(raw_providers, dict):
        raise ValueError("provider_selection.providers must be a mapping.")
    unknown_provider_keys = sorted(set(str(key) for key in raw_providers) - PROVIDER_GROUP_SET)
    if unknown_provider_keys:
        raise ValueError(f"Unknown provider group(s): {', '.join(unknown_provider_keys)}")

    providers: dict[str, dict[str, Any]] = {}
    for group in PROVIDER_GROUPS:
        row = raw_providers.get(group, {})
        if row is None:
            row = {}
        if not isinstance(row, dict):
            raise ValueError(f"provider_selection.providers.{group} must be a mapping.")
        enabled = group in selected
        providers[group] = {
            "enabled": enabled,
            "reason": str(
                row.get("reason")
                or ("Selected by QuestionPlanningAgent." if enabled else "Rejected by QuestionPlanningAgent.")
            ),
        }

    return {
        "selected_groups": selected,
        "providers": providers,
        "rejected_groups": [group for group in PROVIDER_GROUPS if group not in selected],
        "basis": dict(provider_selection.get("basis", {}) or {}),
    }


def provider_row(*, enabled: bool, reason: str) -> dict[str, Any]:
    return {"enabled": bool(enabled), "reason": reason}


def should_enable_web_search(task: str, config: AgentRuntimeConfig) -> bool:
    provider_config = config.get("collector", {}).get("providers", {}).get("web_search", {})
    if provider_config.get("enabled", False):
        return True
    lowered = task.lower()
    return any(
        token in lowered
        for token in (
            "vix",
            "move",
            "oas",
            "cds",
            "bdi",
            "credit spread",
            "volatility index",
            "信用利差",
            "波动率指数",
        )
    )


def apply_provider_selection(
    config: AgentRuntimeConfig,
    provider_selection: dict[str, Any],
) -> AgentRuntimeConfig:
    selected_config: AgentRuntimeConfig = dict(config)
    collector_config = dict(config.get("collector", {}))
    providers = dict(collector_config.get("providers", {}))
    for group, item in provider_selection.get("providers", {}).items():
        providers[group] = {
            **dict(providers.get(group, {})),
            "enabled": bool(item.get("enabled", False)),
        }
    if "tushare" in providers:
        selected_groups = set(provider_selection.get("selected_groups", []))
        tushare_config = dict(providers.get("tushare", {}) or {})
        tushare_config["china_equity"] = "china_equity" in selected_groups
        tushare_config["us_equity"] = "us_equity" in selected_groups
        tushare_config["macro_rates"] = "macro" in selected_groups
        tushare_config["crypto"] = "crypto" in selected_groups and bool(tushare_config.get("crypto", False))
        if "china_equity" not in selected_groups:
            for key in (
                "stock_basic",
                "index_basic",
                "index_daily",
                "a_share_daily",
                "a_share_weekly",
                "daily_basic",
                "a_share_financials",
                "moneyflow_lhb",
                "index_etf",
                "futures_options",
            ):
                tushare_config[key] = False
        if "us_equity" not in selected_groups:
            for key in ("us_basic", "us_daily"):
                tushare_config[key] = False
        if "macro" not in selected_groups:
            for key in (
                "shibor",
                "cn_gdp",
                "cn_cpi",
                "cn_pmi",
                "us_tycr",
                "us_trycr",
                "us_tbr",
                "us_tltr",
                "us_trltr",
            ):
                tushare_config[key] = False
        elif "china_equity" not in selected_groups:
            for key in ("shibor", "cn_gdp", "cn_cpi", "cn_pmi"):
                tushare_config[key] = False
        providers["tushare"] = tushare_config
    collector_config["providers"] = providers
    selected_config["collector"] = collector_config
    return selected_config


def is_a_share_symbol_text(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    return bool(
        re.fullmatch(r"(SH|SZ|BJ)?\d{6}", normalized)
        or re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", normalized)
    )
