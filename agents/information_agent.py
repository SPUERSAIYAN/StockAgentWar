from __future__ import annotations

import importlib
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from agents import information_workflow
from agents.prompt_loader import PromptTemplate, load_prompt_text
from agents.trace_logger import (
    log_agent_error,
    log_agent_messages,
    log_agent_output,
    log_agent_start,
    log_trace,
)
from collectors.digital_oracle_collector import (
    collect_market_information,
    compact_json,
)
from schemas.state import AgentRuntimeConfig, MarketDecisionState, ModelConfig


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ChatModel(Protocol):
    def invoke(self, messages: list[dict[str, str]]) -> Any:
        ...


@dataclass(slots=True)
class MockChatModel:
    name: str

    def invoke(self, messages: list[dict[str, str]]) -> str:
        user_message = messages[-1]["content"] if messages else ""
        model_name = self.name.lower()
        if "question" in model_name or "planning" in model_name:
            return mock_question_planning_report(user_message)
        if "information" in model_name or "info" in model_name:
            return mock_information_report(user_message)
        if "bull" in model_name:
            return mock_bull_case(user_message)
        if "bear" in model_name:
            return mock_bear_case(user_message)
        if "judge" in model_name:
            return mock_judge_decision(user_message)
        if "risk" in model_name:
            return mock_risk_report(user_message)
        if "portfolio" in model_name or "manager" in model_name:
            return mock_portfolio_manager_report(user_message)
        return f"[{self.name}] mock response\n\n{user_message[:500]}"


class InformationCollectionAgent:
    """Information node driven by prompts/information_agent.md."""

    def __init__(self, config: AgentRuntimeConfig):
        self.config = config
        self.model = create_chat_model(config.get("model", {}))
        self.prompt_files = (
            "information_agent.md",
        )
        self.instructions = load_prompt_text(self.prompt_files[0])

    def __call__(self, state: MarketDecisionState) -> dict[str, Any]:
        agent_name = self.config.get("name") or "information"
        log_agent_start(agent_name, state, {"role": self.config.get("role")})
        workflow = information_workflow.build_information_workflow(state)
        provider_selection = information_workflow.select_information_providers(state, workflow, self.config)
        selected_config = information_workflow.apply_provider_selection(self.config, provider_selection)
        log_trace(
            agent_name,
            "WORKFLOW AND PROVIDERS",
            {
                "workflow": workflow,
                "provider_selection": provider_selection,
            },
        )

        runtime_state: MarketDecisionState = {
            **state,
            "information_workflow": workflow,
            "provider_selection": provider_selection,
        }
        try:
            collected = collect_market_information(runtime_state, selected_config)
        except Exception as exc:
            log_agent_error(agent_name, exc)
            raise
        log_trace(agent_name, "COLLECTOR OUTPUT", summarize_collected_data(collected))
        if not collected:
            report = render_no_data_information_report(state, workflow, provider_selection)
            empty_data = {
                "collection_status": "empty",
                "sources": {},
                "errors": {},
                "source_count": 0,
                "error_count": 0,
                "workflow_plan": workflow,
                "provider_selection": provider_selection,
                "signal_reasoning": {},
            }
            structured_context = build_structured_information_context(state, empty_data)
            structured_metadata = dict(structured_context.pop("metadata", {}) or {})
            metadata = {
                **dict(state.get("metadata", {}) or {}),
                "information_source": "digital_oracle",
                "information_prompt": "prompts/information_agent.md",
                "information_context": structured_metadata.get("information_context", {}),
            }
            log_agent_output(agent_name, "info_report", report)
            output: dict[str, Any] = {
                "info_report": report,
                "information_workflow": workflow,
                "provider_selection": provider_selection,
                "raw_market_data": empty_data,
                "signal_reasoning": {},
                **structured_context,
                "metadata": metadata,
            }
            return output

        signal_reasoning = infer_trading_signals(collected)
        enriched_data = {
            **collected,
            "workflow_plan": workflow,
            "provider_selection": provider_selection,
            "signal_reasoning": signal_reasoning,
        }
        report = build_collected_market_report(
            state=state,
            config=selected_config,
            model=self.model,
            collected=enriched_data,
            instructions=self.instructions,
            workflow=workflow,
            provider_selection=provider_selection,
            signal_reasoning=signal_reasoning,
        )
        log_agent_output(agent_name, "info_report", report)
        output_candidates = None
        metadata = {
            **state.get("metadata", {}),
            "information_source": "digital_oracle",
            "information_prompt": "prompts/information_agent.md",
            "information_prompt_references": [
                f"prompts/{file_name}" for file_name in self.prompt_files[1:]
            ],
        }
        if enriched_data.get("candidate_discovery"):
            output_candidates = [
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name", ""),
                    "market": item.get("market", ""),
                    "reason": item.get("reason", ""),
                    "score": item.get("score"),
                    "metadata": item.get("metadata", {}),
                }
                for item in enriched_data["candidate_discovery"].get("candidates", [])
                if isinstance(item, dict) and item.get("symbol")
            ]
            metadata["auto_candidate_discovery"] = enriched_data["candidate_discovery"]

        context_state: MarketDecisionState = {
            **state,
            "raw_market_data": enriched_data,
        }
        if output_candidates is not None:
            context_state["candidates"] = output_candidates
        structured_context = build_structured_information_context(context_state, enriched_data)
        structured_metadata = dict(structured_context.pop("metadata", {}) or {})
        if "information_context" in structured_metadata:
            metadata["information_context"] = structured_metadata["information_context"]

        output = {
            "info_report": report,
            "information_workflow": workflow,
            "provider_selection": provider_selection,
            "signal_reasoning": signal_reasoning,
            "raw_market_data": enriched_data,
            **structured_context,
            "metadata": metadata,
        }
        if output_candidates is not None:
            output["candidates"] = output_candidates
        return output

def run_prompt_agent(
    *,
    config: AgentRuntimeConfig,
    state: MarketDecisionState,
    output_key: str,
    prompt_template: PromptTemplate | None = None,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
) -> dict[str, str]:
    agent_name = config.get("name") or output_key
    log_agent_start(agent_name, state, {"role": config.get("role"), "output_key": output_key})
    variables = prompt_vars(state)
    if prompt_template is not None:
        system_content, user_content = prompt_template.render(variables)
    elif system_prompt is not None and user_prompt is not None:
        system_content = system_prompt.format_map(variables)
        user_content = user_prompt.format_map(variables)
    else:
        raise ValueError("run_prompt_agent requires prompt_template or system_prompt/user_prompt.")

    model = create_chat_model(config.get("model", {}))
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    log_agent_messages(agent_name, config.get("model", {}), messages)
    try:
        content = invoke_text(model, messages)
    except Exception as exc:
        log_agent_error(agent_name, exc)
        raise
    log_agent_output(agent_name, output_key, content)
    return {output_key: content}


def create_chat_model(config: ModelConfig) -> ChatModel:
    provider = config.get("provider", "mock").lower()
    if provider == "mock":
        return MockChatModel(config.get("model", "mock"))
    if provider == "openai":
        return create_openai_model(config)
    if provider == "openrouter":
        return create_openrouter_model(config)
    if provider == "custom":
        return load_custom_model(config)
    raise ValueError(f"Unsupported model provider: {provider}")


def invoke_text(model: ChatModel, messages: list[dict[str, str]]) -> str:
    response = model.invoke(messages)
    if isinstance(response, str):
        return response
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "\n".join(content_part_to_text(part) for part in content)
    return str(content)


def create_openai_model(config: ModelConfig) -> ChatModel:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI provider requires `pip install -r requirements.txt`.") from exc

    kwargs = dict(config.get("kwargs", {}))
    api_key_env = config.get("api_key_env")
    if api_key_env and os.getenv(api_key_env):
        kwargs["api_key"] = os.getenv(api_key_env)
    return ChatOpenAI(
        model=config.get("model", "gpt-4o-mini"),
        temperature=float(config.get("temperature", 0.2)),
        **kwargs,
    )


def create_openrouter_model(config: ModelConfig) -> ChatModel:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("OpenRouter provider requires `pip install -r requirements.txt`.") from exc

    kwargs = dict(config.get("kwargs", {}))
    api_key_env = config.get("api_key_env", "OPENROUTER_API_KEY")
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing OpenRouter API key. Set ${api_key_env} first.")

    default_headers = dict(config.get("default_headers", {}))
    site_url = config.get("site_url") or os.getenv("OPENROUTER_SITE_URL")
    app_title = config.get("app_title") or os.getenv("OPENROUTER_APP_TITLE")
    if site_url:
        default_headers["HTTP-Referer"] = site_url
    if app_title:
        default_headers["X-OpenRouter-Title"] = app_title
    if default_headers:
        kwargs["default_headers"] = default_headers

    return ChatOpenAI(
        model=config.get("model", "openai/gpt-5.2"),
        temperature=float(config.get("temperature", 0.2)),
        api_key=api_key,
        base_url=config.get("base_url") or os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
        **kwargs,
    )


def load_custom_model(config: ModelConfig) -> ChatModel:
    import_path = config.get("import_path")
    if not import_path:
        raise ValueError("Custom model provider requires `import_path`.")
    factory = import_from_path(import_path)
    return factory(**dict(config.get("kwargs", {})))


def import_from_path(import_path: str) -> Any:
    module_name, _, attr = import_path.partition(":")
    if not module_name or not attr:
        raise ValueError("Import path must use `module.path:attribute` format.")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def prompt_vars(state: MarketDecisionState) -> dict[str, str]:
    return {
        "task": state.get("task", "筛选候选股票"),
        "candidates": format_candidates(state.get("candidates", [])),
        "stock_pool": compact_json(state.get("stock_pool", []), 3000),
        "sector_summary": compact_json(state.get("sector_summary", []), 1600),
        "macro_context": compact_json(state.get("macro_context", {}), 1800),
        "info_report": state.get("info_report", "暂无信息分析报告。"),
        "bull_case": state.get("bull_case", "暂无多头观点。"),
        "bull_cases": compact_json(state.get("bull_cases", []), 2200),
        "bull_summary": state.get("bull_summary", "暂无多头总结。"),
        "bear_case": state.get("bear_case", "暂无空头观点。"),
        "bear_cases": compact_json(state.get("bear_cases", []), 2200),
        "bear_summary": state.get("bear_summary", "暂无空头总结。"),
        "judge_decision": state.get("judge_decision", "暂无裁判结论。"),
        "judge_rulings": compact_json(state.get("judge_rulings", []), 2200),
        "judge_report": state.get("judge_report", state.get("judge_decision", "暂无裁判报告。")),
        "risk_report": state.get("risk_report", "暂无风控报告。"),
        "portfolio_context": compact_json(state.get("portfolio_context", {}), 1600),
        "data_gaps": compact_json(state.get("data_gaps", []), 1200),
    }


def build_structured_information_context(
    state: MarketDecisionState,
    raw_data: dict[str, Any],
) -> dict[str, Any]:
    sources = dict(raw_data.get("sources", {}) or {})
    if not sources:
        data_gaps = infer_information_data_gaps(raw_data, [], [])
        if "未获取到可用 provider 数据。" not in data_gaps:
            data_gaps.insert(0, "未获取到可用 provider 数据。")
        return {
            "stock_pool": [],
            "sector_summary": [],
            "confidence_level": infer_information_confidence(raw_data, [], data_gaps),
            "data_gaps": data_gaps,
            "macro_context": {},
            "metadata": {
                **dict(state.get("metadata", {}) or {}),
                "information_context": {
                    "stock_pool_size": 0,
                    "sector_count": 0,
                },
            },
        }

    metrics_by_symbol = extract_symbol_metrics(sources)
    stock_pool = build_information_stock_pool(state, raw_data, metrics_by_symbol)
    sector_summary = build_information_sector_summary(stock_pool)
    data_gaps = infer_information_data_gaps(raw_data, stock_pool, sector_summary)
    macro_context = extract_information_macro_context(sources)
    return {
        "stock_pool": stock_pool,
        "sector_summary": sector_summary,
        "confidence_level": infer_information_confidence(raw_data, stock_pool, data_gaps),
        "data_gaps": data_gaps,
        "macro_context": macro_context,
        "metadata": {
            **dict(state.get("metadata", {}) or {}),
            "information_context": {
                "stock_pool_size": len(stock_pool),
                "sector_count": len(sector_summary),
            },
        },
    }


def extract_symbol_metrics(sources: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for label, value in sources.items():
        if not label.startswith("equity.") or not isinstance(value, dict):
            continue
        parts = label.split(".")
        if len(parts) < 3:
            continue
        symbol = normalize_symbol(parts[1])
        row = metrics.setdefault(symbol, {})
        data_key = ".".join(parts[2:])
        if data_key == "tencent_metrics":
            for item in value.get("items", []) or []:
                if not isinstance(item, dict):
                    continue
                item_symbol = normalize_symbol(str(item.get("symbol") or symbol))
                metrics[item_symbol] = {**metrics.get(item_symbol, {}), **item}
        elif data_key in {"price_daily", "stooq_price_daily"}:
            latest = dict(value.get("latest", {}) or {})
            row.update(
                {
                    "price": latest.get("close"),
                    "change_pct_20d": value.get("return_20_bar_pct"),
                    "avg_volume_20": value.get("avg_volume_20"),
                    "realized_vol_20_annualized": value.get("realized_vol_20_annualized"),
                }
            )
        elif data_key == "options_nearest":
            row["price"] = row.get("price") or value.get("underlying_price")
            row["put_call_oi_ratio"] = value.get("put_call_oi_ratio")
            row["atm_iv"] = value.get("atm_iv")
        elif data_key in {"edgar_form4", "edgar_filings"}:
            row["name"] = row.get("name") or value.get("company_name")
    return metrics


def build_information_stock_pool(
    state: MarketDecisionState,
    raw_data: dict[str, Any],
    metrics_by_symbol: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = list(state.get("candidates", []) or [])
    if not candidates:
        candidates = [{"symbol": symbol} for symbol in raw_data.get("symbols", []) or []]

    stock_pool: list[dict[str, Any]] = []
    for candidate in candidates:
        symbol = normalize_symbol(str(candidate.get("symbol", "")))
        if not symbol:
            continue
        metadata = dict(candidate.get("metadata", {}) or {})
        metric = dict(metrics_by_symbol.get(symbol, {}))
        merged = {**metadata, **metric}
        price = to_float(merged.get("price"))
        score = normalized_information_score(candidate.get("score"), merged)
        stock_pool.append(
            {
                "symbol": symbol,
                "name": candidate.get("name") or merged.get("name") or "",
                "sector": merged.get("sector") or merged.get("industry") or "未分类板块",
                "price": price,
                "pe_ratio": to_float(merged.get("pe")),
                "pb_ratio": to_float(merged.get("pb")),
                "roe": to_float(merged.get("roe")),
                "revenue_growth_yoy": to_float(merged.get("revenue_growth_yoy")),
                "net_profit_growth_yoy": to_float(merged.get("net_profit_growth_yoy")),
                "market_cap_yi": to_float(merged.get("total_market_cap_cny_100m")),
                "turnover_rate": to_float(merged.get("turnover_rate")),
                "north_net_flow_5d": to_float(merged.get("north_net_flow_5d")),
                "technical_signal": infer_information_technical_signal(merged),
                "information_score": score,
                "preliminary_reason": candidate.get("reason") or "候选标的来自信息分析流程。",
            }
        )
    return sorted(stock_pool, key=lambda item: item.get("information_score") or 0, reverse=True)


def build_information_sector_summary(stock_pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sectors: dict[str, list[dict[str, Any]]] = {}
    for stock in stock_pool:
        sectors.setdefault(str(stock.get("sector") or "未分类板块"), []).append(stock)

    summary = []
    for sector_name, rows in sectors.items():
        pe_values = [to_float(row.get("pe_ratio")) for row in rows]
        turnover_values = [to_float(row.get("turnover_rate")) for row in rows]
        change_values = [to_float(row.get("change_pct_20d")) for row in rows]
        avg_turnover = average([item for item in turnover_values if item is not None])
        summary.append(
            {
                "sector_name": sector_name,
                "change_pct_5d": None,
                "change_pct_20d": average([item for item in change_values if item is not None]),
                "avg_pe": average([item for item in pe_values if item is not None]),
                "money_flow_signal": infer_money_flow_signal(avg_turnover),
                "policy_catalyst": "未接入政策事件结构化数据",
            }
        )
    return summary


def infer_information_data_gaps(
    raw_data: dict[str, Any],
    stock_pool: list[dict[str, Any]],
    sector_summary: list[dict[str, Any]],
) -> list[str]:
    gaps: list[str] = []
    errors = dict(raw_data.get("errors", {}) or {})
    if errors:
        gaps.append(f"{len(errors)} 个数据源采集失败，需降低置信度。")
    discovery = dict(raw_data.get("candidate_discovery", {}) or {})
    if discovery.get("mode") == "provider_sector_discovery" and not discovery.get("candidates"):
        gaps.append(
            "当前未接入板块成分股数据源，无法按板块限定候选："
            f"{discovery.get('requested_sectors', [])}。"
        )
    if not stock_pool:
        gaps.append("未形成结构化股票池。")
    if stock_pool and any(stock.get("price") is None for stock in stock_pool):
        gaps.append("部分候选标的缺少可用价格数据。")
    if not sector_summary or any(item.get("sector_name") == "未分类板块" for item in sector_summary):
        gaps.append("行业/板块分类数据不足。")
    if any(stock.get("roe") is None for stock in stock_pool):
        gaps.append("ROE、营收增速、净利润增速等财务增强字段不足。")
    return gaps


def infer_information_confidence(
    raw_data: dict[str, Any],
    stock_pool: list[dict[str, Any]],
    data_gaps: list[str],
) -> float:
    source_count = int(raw_data.get("source_count") or 0)
    error_count = int(raw_data.get("error_count") or len(dict(raw_data.get("errors", {}) or {})))
    score = 0.35
    if stock_pool:
        score += 0.25
    if source_count:
        score += min(source_count / 20, 0.25)
    if error_count:
        score -= min(error_count / 20, 0.2)
    score -= min(len(data_gaps) * 0.04, 0.2)
    return round(max(min(score, 0.9), 0.1), 2)


def extract_information_macro_context(sources: dict[str, Any]) -> dict[str, Any]:
    return {
        label: value
        for label, value in sources.items()
        if label.startswith("macro.") or label.startswith("prediction.") or label.startswith("crypto.")
    }


def normalized_information_score(candidate_score: Any, metrics: dict[str, Any]) -> float:
    score = to_float(candidate_score)
    if score is None:
        score = 50.0
    elif score <= 10:
        score = score * 12

    change_pct = to_float(metrics.get("change_pct") or metrics.get("change_pct_20d"))
    if change_pct is not None:
        score += max(min(change_pct, 12), -12)

    pe = to_float(metrics.get("pe"))
    pb = to_float(metrics.get("pb"))
    if pe and pe > 100:
        score -= 8
    if pb and pb > 15:
        score -= 5
    return round(max(min(score, 100), 0), 2)


def infer_information_technical_signal(metrics: dict[str, Any]) -> str:
    change_pct = to_float(metrics.get("change_pct") or metrics.get("change_pct_20d"))
    volume_ratio = to_float(metrics.get("volume_ratio"))
    if change_pct is not None and volume_ratio is not None:
        if change_pct > 0 and volume_ratio >= 1.2:
            return "放量上涨"
        if change_pct < 0 and volume_ratio >= 1.2:
            return "放量下跌"
    if change_pct is not None:
        if change_pct > 3:
            return "价格转强"
        if change_pct < -3:
            return "价格转弱"
    return "待补充均线/MACD/KDJ"


def infer_money_flow_signal(avg_turnover: float | None) -> str:
    if avg_turnover is None:
        return "资金面数据不足"
    if avg_turnover >= 5:
        return "成交活跃"
    if avg_turnover >= 2:
        return "成交温和"
    return "成交偏弱"


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if re.fullmatch(r"SH\d{6}", normalized):
        return f"{normalized[2:]}.SH"
    if re.fullmatch(r"SZ\d{6}", normalized):
        return f"{normalized[2:]}.SZ"
    if re.fullmatch(r"\d{6}\.(SH|SZ)", normalized):
        return normalized
    if re.fullmatch(r"\d{6}", normalized):
        if normalized.startswith(("600", "601", "603", "605", "688")):
            return f"{normalized}.SH"
        return f"{normalized}.SZ"
    return normalized


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def format_candidates(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "未提供明确候选股票。"
    rows = []
    for item in candidates:
        rows.append(" / ".join(str(item.get(key, "")) for key in ("symbol", "name", "market") if item.get(key)))
    return "\n".join(f"- {row}" for row in rows)


def content_part_to_text(part: Any) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        return str(part.get("text") or part.get("content") or part)
    return str(part)


def mock_question_plan(user_message: str) -> str:
    task_match = re.search(r"Task:\s*(.*)", user_message)
    task = task_match.group(1).strip() if task_match else ""
    lowered = user_message.lower()
    is_a_share = any(
        token in lowered
        for token in ("a-share", "a股", "a 股", "china a-share", "中国股", "沪深", "明天", "哪只股票")
    )
    if is_a_share:
        payload = {
            "question_understanding": {
                "rewritten_question": "A股市场极短期具有上涨潜力的个股/板块识别",
                "core_intent": "寻找当前市场定价中存在正向预期差的方向",
                "market_scope": "China A-share",
                "primary_time_window": "1-5 trading days",
                "secondary_time_window": "1-3 months trend confirmation",
                "candidate_scope": "A-share candidate discovery when explicit symbols are absent",
                "risk_notes": ["研究支持，不构成个性化投资建议。"],
            },
            "signal_plan": {
                "selected_provider_groups": ["china_equity", "macro"],
                "selected_signals": [
                    {
                        "id": "china.candidate_discovery",
                        "provider_group": "china_equity",
                        "description": "A-share candidate discovery, realtime quotes, valuation, turnover, volume ratio and amount.",
                        "reason": "Needed to identify tradable A-share candidates.",
                    },
                    {
                        "id": "macro.china_risk_pricing",
                        "provider_group": "macro",
                        "description": "USDCNY, VIX and broad risk proxies.",
                        "reason": "Needed to cross-check short-term market risk appetite.",
                    },
                ],
                "rejected_provider_groups": [
                    {"provider_group": "us_equity", "reason": "A-share task does not need US single-stock data."},
                    {"provider_group": "prediction_markets", "reason": "No explicit event-probability question."},
                    {"provider_group": "crypto", "reason": "No crypto-linked thesis."},
                    {"provider_group": "web_search", "reason": "No concrete structured-data gap requested."},
                ],
                "data_needed_by_information_agent": [
                    "A-share candidate discovery and realtime trading metrics.",
                    "China risk-pricing macro proxies.",
                ],
            },
        }
    else:
        payload = {
            "question_understanding": {
                "rewritten_question": task or "Global equity candidate assessment",
                "core_intent": "Assess tradable upside/downside using structured market data",
                "market_scope": "US/global listed assets",
                "primary_time_window": "3-12 months",
                "secondary_time_window": "1-3 years context",
                "candidate_scope": "User-supplied symbols",
                "risk_notes": ["Research support only; do not frame as personalized investment advice."],
            },
            "signal_plan": {
                "selected_provider_groups": ["us_equity", "macro"],
                "selected_signals": [
                    {
                        "id": "equity.price_options",
                        "provider_group": "us_equity",
                        "description": "Price history, weekly trend, realized volatility, options and EDGAR where available.",
                        "reason": "Needed for listed US/global symbols.",
                    },
                    {
                        "id": "macro.risk_pricing",
                        "provider_group": "macro",
                        "description": "Rates, VIX and broad risk proxies.",
                        "reason": "Needed to cross-check market risk appetite.",
                    },
                ],
                "rejected_provider_groups": [
                    {"provider_group": "china_equity", "reason": "No A-share scope detected."},
                    {"provider_group": "prediction_markets", "reason": "No explicit event-probability question."},
                    {"provider_group": "crypto", "reason": "No crypto-linked thesis."},
                    {"provider_group": "web_search", "reason": "No concrete structured-data gap requested."},
                ],
                "data_needed_by_information_agent": [
                    "US/global equity price, options, and filing data.",
                    "Macro risk proxies.",
                ],
            },
        }
    return json.dumps(payload, ensure_ascii=False)


def build_information_workflow(state: MarketDecisionState) -> dict[str, Any]:
    task = state.get("task", "")
    symbols = [str(item.get("symbol", "")).upper() for item in state.get("candidates", []) if item.get("symbol")]
    discovery = dict(state.get("metadata", {}).get("auto_candidate_discovery", {}) or {})
    return {
        "instruction_file": "prompts/information_agent.md",
        "workflow_steps": [
            "Step 1: Understand the question",
            "Step 2: Select signals",
            "Step 3: Signal routing",
            "Step 4: Fetch data with Python providers",
            "Step 5: Analyze trading-data signals",
            "Step 6: Output structured report",
        ],
        "question_decomposition": {
            "core_variable": infer_core_variable(task, symbols),
            "time_window": infer_time_window(task),
            "priceability": "high" if symbols else "medium",
            "candidates": symbols,
            "candidate_source": "auto_discovery" if discovery else "user_input",
            "candidate_discovery": discovery,
        },
        "routing_criteria": ["relevance", "time_match", "information_increment"],
    }


def infer_core_variable(task: str, symbols: list[str]) -> str:
    if symbols:
        return f"Candidate stock/asset decision for {', '.join(symbols)}"
    return task.strip() or "Candidate stock decision"


def infer_time_window(task: str) -> str:
    lowered = task.lower()
    if any(token in lowered for token in ("3-5", "5 year", "5年", "长期", "long-term")):
        return "long_term_3_to_5_years"
    if any(token in lowered for token in ("1-3", "1 year", "3 year", "中期", "一年", "三年")):
        return "medium_term_1_to_3_years"
    if any(token in lowered for token in ("month", "月", "quarter", "季度", "短期", "3 months")):
        return "short_term_3_to_12_months"
    return "short_to_medium_term"


def select_information_providers(
    state: MarketDecisionState,
    workflow: dict[str, Any],
    config: AgentRuntimeConfig,
) -> dict[str, Any]:
    task = state.get("task", "")
    lowered = task.lower()
    symbols = workflow["question_decomposition"]["candidates"]
    has_a_share = any(is_a_share_symbol_text(symbol) for symbol in symbols)
    has_global_symbol = any(not is_a_share_symbol_text(symbol) for symbol in symbols)

    selected: dict[str, dict[str, Any]] = {
        "us_equity": {
            "enabled": has_global_symbol,
            "reason": "候选标的是美股/ETF/全球 Yahoo 代码，需要价格、期权和 EDGAR 等交易数据。",
        },
        "china_equity": {
            "enabled": has_a_share,
            "reason": "候选标的是 A 股，需要 Tencent/Mootdx 的行情、估值和盘口类数据。",
        },
        "macro": {
            "enabled": True,
            "reason": "利率、收益率曲线、CFTC、市场情绪和宏观风险会影响股票风险溢价。",
        },
        "prediction_markets": {
            "enabled": True,
            "reason": "Kalshi/Polymarket 提供真实资金定价的事件概率，用于交叉验证市场预期。",
        },
        "crypto": {
            "enabled": any(
                token in lowered
                for token in ("crypto", "bitcoin", "btc", "eth", "recession", "bubble", "crash", "risk", "衰退", "泡沫", "崩盘", "风险")
            ),
            "reason": "加密价格、期货曲线和期权可作为风险偏好代理；仅在宏观/风险/加密相关问题中启用。",
        },
        "web_search": {
            "enabled": should_enable_web_search(task, config),
            "reason": "仅用于缺少结构化 provider 的交易数据补充，例如 VIX/MOVE/OAS/CDS/BDI。",
        },
    }

    selected_groups = [group for group, item in selected.items() if item["enabled"]]
    return {
        "selected_groups": selected_groups,
        "providers": selected,
        "rejected_groups": [group for group in selected if group not in selected_groups],
        "basis": {
            "question_type": infer_question_type(task, symbols),
            "time_window": workflow["question_decomposition"]["time_window"],
            "minimum_independent_dimensions": 3,
        },
    }


def should_enable_web_search(task: str, config: AgentRuntimeConfig) -> bool:
    provider_config = config.get("collector", {}).get("providers", {}).get("web_search", {})
    if provider_config.get("enabled", False):
        return True
    lowered = task.lower()
    return any(token in lowered for token in ("vix", "move", "oas", "cds", "bdi", "信用利差", "波动率指数"))


def infer_question_type(task: str, symbols: list[str]) -> str:
    lowered = task.lower()
    if any(token in lowered for token in ("recession", "macro", "fed", "rate", "衰退", "宏观", "利率")):
        return "economic_recession_or_macro_cycle"
    if any(token in lowered for token in ("crash", "options", "option", "崩盘", "期权")):
        return "stock_options_or_crash_probability"
    if any(token in lowered for token in ("bubble", "industry", "sector", "泡沫", "行业")):
        return "industry_cycle_or_bubble_assessment"
    if any(is_a_share_symbol_text(symbol) for symbol in symbols):
        return "china_a_share_analysis"
    return "asset_pricing_or_stock_selection"


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
    collector_config["providers"] = providers
    selected_config["collector"] = collector_config
    return selected_config


def infer_trading_signals(collected: dict[str, Any]) -> dict[str, Any]:
    sources = dict(collected.get("sources", {}))
    rows = [interpret_source_signal(label, value) for label, value in sources.items()]
    candidate_comparison = build_candidate_comparison(sources)
    bullish = sum(1 for row in rows if row["bias"] == "bullish")
    bearish = sum(1 for row in rows if row["bias"] == "bearish")
    neutral = sum(1 for row in rows if row["bias"] == "neutral")
    total = max(bullish + bearish + neutral, 1)

    if bullish > bearish:
        most_likely = "constructive_but_needs_risk_confirmation"
    elif bearish > bullish:
        most_likely = "defensive_or_watch_until_risk_eases"
    else:
        most_likely = "mixed_signals_watch"

    return {
        "signal_table": rows,
        "counts": {
            "bullish": bullish,
            "bearish": bearish,
            "neutral_or_context": neutral,
        },
        "resonance_signals": [row for row in rows if row["bias"] in {"bullish", "bearish"}][:10],
        "key_divergences": build_signal_divergences(rows),
        "candidate_comparison": candidate_comparison,
        "time_stratification": {
            "short_term_3_to_12_months": [row for row in rows if row["time_horizon"] == "short_term"][:8],
            "medium_term_1_to_3_years": [row for row in rows if row["time_horizon"] == "medium_term"][:8],
            "long_term_3_to_5_years": [row for row in rows if row["time_horizon"] == "long_term"][:8],
        },
        "probability_estimates": [
            {
                "scenario": "Bullish follow-through",
                "probability": round((bullish + 0.5 * neutral) / total, 2),
                "basis": "Directional share of positive price/derivatives/event-market signals.",
            },
            {
                "scenario": "Bearish drawdown or underperformance",
                "probability": round((bearish + 0.25 * neutral) / total, 2),
                "basis": "Directional share of negative price/volatility/positioning signals.",
            },
            {
                "scenario": "Range-bound watch",
                "probability": round(neutral / total, 2),
                "basis": "Neutral or contextual signals without clear directional edge.",
            },
        ],
        "most_likely_path": most_likely,
    }


def build_candidate_comparison(sources: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, value in sources.items():
        if not (label.startswith("equity.") and "tencent_metrics" in label):
            continue
        if not isinstance(value, dict):
            continue
        items = list(value.get("items", []) or [])
        if not items or not isinstance(items[0], dict):
            continue
        item = items[0]
        score, basis = score_tencent_candidate(item)
        rows.append(
            {
                "symbol": item.get("symbol") or label.split(".")[1],
                "name": item.get("name") or "",
                "score": score,
                "basis": basis,
                "metrics": {
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
    return sorted(rows, key=lambda row: row["score"], reverse=True)


def score_tencent_candidate(metrics: dict[str, Any]) -> tuple[float, str]:
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

    return round(score, 3), "; ".join(basis) or "Tencent metrics available"


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def interpret_source_signal(label: str, value: Any) -> dict[str, Any]:
    text = compact_json(value, 260)
    bias = "neutral"
    meaning = "Context signal; use for cross-validation rather than as a standalone decision."
    horizon = "short_term"

    if isinstance(value, dict) and "return_20_bar_pct" in value:
        ret = value.get("return_20_bar_pct")
        vol = value.get("realized_vol_20_annualized")
        if isinstance(ret, (int, float)) and ret > 3:
            bias = "bullish"
            meaning = "Recent price trend is positive; market is rewarding the asset over the latest window."
        elif isinstance(ret, (int, float)) and ret < -3:
            bias = "bearish"
            meaning = "Recent price trend is negative; market is discounting risk or weaker expectations."
        else:
            meaning = "Recent trend is not decisive; use relative and derivatives signals for confirmation."
        if isinstance(vol, (int, float)) and vol > 0.45:
            meaning += " Realized volatility is elevated, so position sizing should be conservative."
    elif isinstance(value, dict) and {"atm_iv", "put_call_oi_ratio"}.intersection(value):
        put_call = value.get("put_call_oi_ratio") or value.get("put_call_volume_ratio")
        if isinstance(put_call, (int, float)) and put_call > 1.5:
            bias = "bearish"
            meaning = "Options positioning leans defensive; downside protection demand is elevated."
        else:
            meaning = "Options market does not show an extreme bearish skew in the summarized chain."
    elif "edgar" in label:
        horizon = "medium_term"
        meaning = "Insider transaction data provides fundamental confidence/risk context; concentrated selling would be bearish."
    elif "yield_curve" in label or "treasury" in label:
        horizon = "medium_term"
        if isinstance(value, dict):
            spread = value.get("spread_10y_3m")
            if isinstance(spread, (int, float)) and spread < 0:
                bias = "bearish"
                meaning = "Yield curve inversion signals macro tightening/recession pressure."
    elif "fear_greed" in label:
        meaning = "Fear & Greed is a composite market sentiment signal; extremes confirm risk-on/risk-off tone."
    elif "polymarket" in label or "kalshi" in label:
        meaning = "Prediction market signal reflects real-money event probability; discount if liquidity is low."
    elif "cftc" in label:
        horizon = "medium_term"
        meaning = "CFTC positioning shows institutional futures exposure; use net positioning changes as smart-money context."
    elif "coingecko" in label or "deribit" in label:
        meaning = "Crypto spot/derivatives signal acts as risk appetite proxy unless the target asset is crypto."
    elif "worldbank" in label or "bis" in label:
        horizon = "long_term"
        meaning = "Slow-moving macro structural data; useful for long-term background, not tactical timing."
    elif "tencent" in label or "mootdx" in label:
        meaning = "A-share structured quote/valuation signal; combine price, turnover and valuation before drawing direction."

    return {
        "signal": label,
        "data": text,
        "bias": bias,
        "time_horizon": horizon,
        "what_it_is_saying": meaning,
    }


def build_signal_divergences(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    bullish = [row["signal"] for row in rows if row["bias"] == "bullish"]
    bearish = [row["signal"] for row in rows if row["bias"] == "bearish"]
    if bullish and bearish:
        return [
            {
                "divergence": "Bullish and bearish signals coexist.",
                "interpretation": (
                    f"Bullish: {', '.join(bullish[:4])}; bearish: {', '.join(bearish[:4])}. "
                    "Compare liquidity, directness and time horizon before assigning weight."
                ),
            }
        ]
    return [
        {
            "divergence": "No strong directional divergence detected in summarized signals.",
            "interpretation": "Focus on confidence, data gaps and monitor thresholds.",
        }
    ]


def is_a_share_symbol_text(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    return bool(
        re.fullmatch(r"(SH|SZ)?\d{6}", normalized)
        or re.fullmatch(r"\d{6}\.(SH|SZ)", normalized)
    )


def build_collected_market_report(
    *,
    state: MarketDecisionState,
    config: AgentRuntimeConfig,
    model: ChatModel,
    collected: dict[str, Any],
    instructions: str,
    workflow: dict[str, Any],
    provider_selection: dict[str, Any],
    signal_reasoning: dict[str, Any],
) -> str:
    if isinstance(model, MockChatModel):
        return render_deterministic_report(
            task=state.get("task", "筛选候选股票"),
            candidates=state.get("candidates", []),
            data=collected,
            workflow=workflow,
            provider_selection=provider_selection,
            signal_reasoning=signal_reasoning,
        )

    data_json = json.dumps(collected, ensure_ascii=False, indent=2, default=str)
    max_chars = int(config.get("collector", {}).get("llm_context_chars", 24000))
    if len(data_json) > max_chars:
        data_json = data_json[:max_chars] + "\n...TRUNCATED..."

    prompt = build_information_report_prompt(
        state=state,
        workflow=workflow,
        provider_selection=provider_selection,
        signal_reasoning=signal_reasoning,
        data_json=data_json,
    )
    log_agent_messages(
        config.get("name") or "information",
        config.get("model", {}),
        [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ],
    )
    try:
        return invoke_text(
            model,
            [
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        fallback = render_deterministic_report(
            task=state.get("task", "筛选候选股票"),
            candidates=state.get("candidates", []),
            data=collected,
            workflow=workflow,
            provider_selection=provider_selection,
            signal_reasoning=signal_reasoning,
        )
        return f"{fallback}\n\n## 信息报告 LLM 生成失败\n\n- {type(exc).__name__}: {exc}"


def build_information_report_prompt(
    *,
    state: MarketDecisionState,
    workflow: dict[str, Any],
    provider_selection: dict[str, Any],
    signal_reasoning: dict[str, Any],
    data_json: str,
) -> str:
    return (
        f"Task: {state.get('task', 'screen candidate stocks')}\n"
        f"Candidate stocks:\n{format_candidates(state.get('candidates', []))}\n\n"
        "The Python workflow layer has already executed Steps 1-5. "
        "Write only the Step 6 structured report required by the system prompt. "
        "Use only the JSON inputs below; do not invent data and do not claim that you fetched anything yourself.\n\n"
        f"Workflow plan:\n```json\n{json.dumps(workflow, ensure_ascii=False, indent=2)}\n```\n\n"
        f"Provider selection:\n```json\n{json.dumps(provider_selection, ensure_ascii=False, indent=2)}\n```\n\n"
        f"Pre-computed trading signal reasoning:\n```json\n{json.dumps(signal_reasoning, ensure_ascii=False, indent=2, default=str)}\n```\n\n"
        f"Fetched provider data:\n```json\n{data_json}\n```\n"
    )


def summarize_collected_data(collected: dict[str, Any]) -> dict[str, Any]:
    if not collected:
        return {"collection_status": "empty"}
    sources = dict(collected.get("sources", {}) or {})
    errors = dict(collected.get("errors", {}) or {})
    return {
        "collection_status": collected.get("collection_status"),
        "generated_at": collected.get("generated_at"),
        "source_count": collected.get("source_count", len(sources)),
        "error_count": collected.get("error_count", len(errors)),
        "sources": list(sources.keys()),
        "errors": {key: str(value) for key, value in errors.items()},
    }


def render_no_data_information_report(
    state: MarketDecisionState,
    workflow: dict[str, Any],
    provider_selection: dict[str, Any],
) -> str:
    return (
        "# 信息分析：Multi-Signal Synthesis\n\n"
        "## Data Summary\n\n"
        "- 未能获取 provider 数据，无法进行交易数据驱动的多信号推理。\n\n"
        "## Analysis\n\n"
        f"- Workflow: `{compact_json(workflow, 1200)}`\n"
        f"- Provider selection: `{compact_json(provider_selection, 1200)}`\n\n"
        "## Probability Estimates\n\n"
        "| Scenario | Probability | Basis |\n"
        "|----------|-------------|-------|\n"
        "| 暂停判断 | 100% | 缺少可用交易数据 |\n\n"
        "## Conclusion\n\n"
        "> 数据不足，信息分析 Agent 不应给出候选股票结论。\n"
    )


def render_deterministic_report(
    *,
    task: str,
    candidates: list[dict[str, Any]],
    data: dict[str, Any],
    workflow: dict[str, Any],
    provider_selection: dict[str, Any],
    signal_reasoning: dict[str, Any],
) -> str:
    source_rows = []
    for row in signal_reasoning.get("signal_table", [])[:18]:
        source_rows.append(
            f"| `{row['signal']}` | {row['data']} | {row['what_it_is_saying']} |"
        )
    if not source_rows:
        source_rows.append("| 暂无 | 暂无 | 暂无可解释信号 |")

    probabilities = []
    for item in signal_reasoning.get("probability_estimates", []):
        probabilities.append(f"| {item['scenario']} | {item['probability']} | {item['basis']} |")

    comparison_rows = []
    for item in signal_reasoning.get("candidate_comparison", [])[:12]:
        comparison_rows.append(
            f"| {item.get('symbol', '')} | {item.get('name', '')} | {item.get('score', '')} | {item.get('basis', '')} |"
        )

    return "\n".join(
        [
            f"# {task}: Multi-Signal Synthesis",
            "",
            "## Data Summary",
            "",
            "### Workflow Decomposition",
            f"- Core variable: {workflow['question_decomposition']['core_variable']}",
            f"- Time window: {workflow['question_decomposition']['time_window']}",
            f"- Priceability: {workflow['question_decomposition']['priceability']}",
            "",
            "### Provider Selection",
            f"- Selected groups: {', '.join(provider_selection.get('selected_groups', []))}",
            f"- Rejected groups: {', '.join(provider_selection.get('rejected_groups', []))}",
            f"- Collection status: {data.get('collection_status', 'unknown')}",
            f"- Success sources: {data.get('source_count', 0)}",
            f"- Failed sources: {data.get('error_count', 0)}",
            "",
            "### Layer 1: Provider Signals",
            "| Signal | Data | What it's saying |",
            "|--------|------|-----------------|",
            *source_rows,
            "",
            "### Candidate Comparison",
            "| Symbol | Name | Score | Basis |",
            "|--------|------|-------|-------|",
            *(comparison_rows or ["| N/A | N/A | N/A | No comparable candidate metrics were collected. |"]),
            "",
            "## Analysis",
            "",
            "### Resonance signals",
            compact_json(signal_reasoning.get("resonance_signals", []), 1600),
            "",
            "### Key divergences",
            compact_json(signal_reasoning.get("key_divergences", []), 1200),
            "",
            "### Time stratification",
            compact_json(signal_reasoning.get("time_stratification", {}), 1600),
            "",
            "## Probability Estimates",
            "| Scenario | Probability | Basis |",
            "|----------|-------------|-------|",
            *(probabilities or ["| 暂停判断 | 1.0 | 缺少足够方向性信号 |"]),
            "",
            f"### Most likely path: {signal_reasoning.get('most_likely_path', 'mixed_signals_watch')}",
            "**Core logic chain:** 以上结论只来自 provider 拉取的交易数据摘要。方向性信号需要由多头、空头和风控 Agent 继续交叉检查，失败 provider 必须视为数据缺口。",
            "",
            "## Conclusion",
            "",
            "> 信息分析已完成 workflow 拆解、provider 选择、Python provider 拉取、交易数据推理和结构化输出；此结果不构成投资建议。",
            "",
            "### Sub-conclusions",
            "| Dimension | Judgment | Confidence |",
            "|-----------|----------|------------|",
            f"| Short-term (6-12mo) | {signal_reasoning.get('most_likely_path', 'mixed')} | Medium |",
            "| Medium-term (1-3yr) | 需要结合宏观、CFTC、EDGAR 等慢变量确认 | Medium |",
            "| Data quality | 成功来源与失败来源见 Data Summary | Medium |",
            "",
            "### Risk factors",
            "- **Upside risk:** 价格趋势、期权和事件市场进一步共振。",
            "- **Downside risk:** 宏观、流动性、期权保护需求或 provider 缺口恶化。",
            "",
            "### Signals to monitor",
            "| Signal | Current value | Threshold | Meaning |",
            "|--------|--------------|-----------|---------|",
            "| price trend | see provider signals | 20-bar return flips sign | momentum regime change |",
            "| options skew | see options chain | put/call > 1.5 | defensive demand rising |",
            "| yield curve | see macro.yield_curve | 10Y-3M stays inverted | macro pressure persists |",
            "",
            f"*Data sources: {', '.join(data.get('sources', {}).keys())}*",
            f"*Fetched at: {data.get('generated_at', '')}*",
        ]
    )


def mock_information_report(user_message: str) -> str:
    return f"## 信息分析 Mock 输出\n\n{user_message[:900]}"


def mock_question_planning_report(user_message: str) -> str:
    planning_input = user_message.split("Data-source reference document:", 1)[0]
    lowered = planning_input.lower()
    is_china = any(
        token in lowered
        for token in (
            "a股",
            "a-share",
            "china",
            "沪深",
            "大a",
            "板块",
            "行业",
            "概念",
            "地域",
            "通达信",
        )
    )
    if is_china:
        selected_groups = ["china_equity", "macro"]
        market_scope = "China A-share"
    else:
        selected_groups = ["us_equity", "macro"]
        market_scope = "US/global listed assets"
    providers = {
        group: {
            "enabled": group in selected_groups,
            "reason": (
                "Mock planner selected this provider group."
                if group in selected_groups
                else "Mock planner rejected this provider group."
            ),
        }
        for group in (
            "us_equity",
            "china_equity",
            "macro",
            "prediction_markets",
            "crypto",
            "web_search",
        )
    }
    return json.dumps(
        {
            "question_understanding": {
                "rewritten_question": "Mock question planning result",
                "core_intent": "Select provider groups before information collection",
                "market_scope": market_scope,
                "time_window": "short_to_medium_term",
                "candidate_scope": "User supplied or provider discovered candidates",
            },
            "provider_selection": {
                "selected_groups": selected_groups,
                "providers": providers,
                "rejected_groups": [group for group in providers if group not in selected_groups],
            },
        },
        ensure_ascii=False,
    )


def mock_bull_case(user_message: str) -> str:
    return (
        "## 多头观点\n\n"
        "- 优先关注盈利预期上修、资金流入、技术形态转强的标的。\n"
        "- 看多触发条件：放量突破关键阻力、行业催化落地、财报超预期。\n"
        "- 失效条件：跌破关键支撑、市场风险偏好下降、核心假设被证伪。\n\n"
        f"### 输入摘录\n{user_message[:500]}"
    )


def mock_bear_case(user_message: str) -> str:
    return (
        "## 空头观点\n\n"
        "- 警惕估值过高、利好兑现、盈利质量下降和流动性退潮。\n"
        "- 回避触发条件：高位缩量、跌破均线、宏观压力升温。\n"
        "- 失效条件：重新放量走强、业绩超预期、风险事件解除。\n\n"
        f"### 输入摘录\n{user_message[:500]}"
    )


def mock_judge_decision(user_message: str) -> str:
    return (
        "## 裁判决策\n\n"
        "| 股票 | 方向 | 优先级 | 核心理由 | 主要风险 | 观察信号 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| 待接入真实数据 | WATCH | 中 | mock 模式仅验证多 Agent 协作链路 | 缺少实时数据 | 信息分析后再排序 |\n\n"
        f"### 输入摘录\n{user_message[:700]}"
    )


def mock_risk_report(user_message: str) -> str:
    return (
        "## 风控复核\n\n"
        "| 股票 | 方向 | 优先级 | 建议仓位 | 止损/失效条件 | 主要风险 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| 待接入真实数据 | WATCH | 中 | 0%-5% | 数据补齐前不进入实盘 | 缺少实时行情、成交量、财报和新闻验证 |\n\n"
        "- 输出仅用于研究流程验证，不构成投资建议。\n\n"
        f"### 裁判输入摘录\n{user_message[:700]}"
    )


def mock_portfolio_manager_report(user_message: str) -> str:
    return (
        "## 总经理决策\n\n"
        "- 仅在裁判裁决、风控意见和价格触发条件同时满足时生成交易计划。\n"
        "- 单票仓位、总仓位、止损止盈按配置约束执行，数量按 100 股整数倍取整。\n"
        "- 数据缺口存在时降低置信度，不允许绕过风控直接实盘。\n\n"
        f"### 输入摘录\n{user_message[:700]}"
    )
