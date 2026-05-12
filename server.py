from __future__ import annotations

import json
import os
import time
import warnings
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
except Exception:
    LangChainPendingDeprecationWarning = PendingDeprecationWarning

warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects`.*",
    module=r"langgraph\.cache\.base.*",
)

from graph.a_share_auto_trade_graph import build_a_share_auto_trade_graph
from graph.stock_graph import DEFAULT_AGENT_CONFIGS, build_stock_graph
from main import load_agent_configs, parse_symbols


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"

load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(title="Stock Decision System")


class DecisionRequest(BaseModel):
    task: str = Field(default="筛选未来 1-3 个月的候选股票")
    symbols: str = Field(default="AAPL,MSFT,NVDA")
    sectors: str = Field(default="")
    mode: Literal["openrouter", "mock", "a_share_daily", "a_share_sector", "a_share_deep"] = "openrouter"
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] = "moderate"
    capital: float = Field(default=1_000_000)
    config_path: str = Field(default="config.yaml")


COMMON_STAGES: dict[str, dict[str, str]] = {
    "information_analysis": {
        "id": "information_analysis",
        "agent": "信息分析",
        "title": "市场信息汇总",
        "output_key": "info_report",
        "color": "#3B82F6",
    },
    "bull_debate": {
        "id": "bull_debate",
        "agent": "多头",
        "title": "上涨逻辑",
        "output_key": "bull_case",
        "color": "#22C55E",
    },
    "bear_debate": {
        "id": "bear_debate",
        "agent": "空头",
        "title": "风险反驳",
        "output_key": "bear_case",
        "color": "#EF4444",
    },
    "judge_decision": {
        "id": "judge_decision",
        "agent": "裁判",
        "title": "综合裁决",
        "output_key": "judge_decision",
        "color": "#A78BFA",
    },
    "risk_review": {
        "id": "risk_review",
        "agent": "风控",
        "title": "风险复核",
        "output_key": "risk_report",
        "color": "#F59E0B",
    },
}

A_SHARE_STAGES: dict[str, dict[str, str]] = {
    **COMMON_STAGES,
    "a_share_context": {
        "id": "a_share_context",
        "agent": "A 股上下文",
        "title": "股票池与板块",
        "output_key": "a_share_context_report",
        "color": "#06B6D4",
    },
    "portfolio_manager": {
        "id": "portfolio_manager",
        "agent": "总经理",
        "title": "最终决策",
        "output_key": "manager_report",
        "color": "#EC4899",
    },
    "save_trade_plan": {
        "id": "save_trade_plan",
        "agent": "交易计划",
        "title": "计划落盘",
        "output_key": "trade_plan_report",
        "color": "#14B8A6",
    },
}

A_SHARE_STAGE_ORDER = [
    "information_analysis",
    "a_share_context",
    "bull_debate",
    "bear_debate",
    "judge_decision",
    "risk_review",
    "portfolio_manager",
    "save_trade_plan",
]

COMMON_STAGE_ORDER = [
    "information_analysis",
    "bull_debate",
    "bear_debate",
    "judge_decision",
    "risk_review",
]


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "config_exists": DEFAULT_CONFIG_PATH.exists(),
        "openrouter_key_ready": bool(os.getenv("OPENROUTER_API_KEY")),
        "stages": list(COMMON_STAGES.values()),
        "stage_sets": {
            "common": ordered_stage_list(COMMON_STAGES, COMMON_STAGE_ORDER),
            "a_share": ordered_stage_list(A_SHARE_STAGES, A_SHARE_STAGE_ORDER),
        },
    }


@app.post("/api/decide/stream")
def decide_stream(request: DecisionRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_decision(request),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def stream_decision(request: DecisionRequest):
    started_at = time.perf_counter()
    state: dict[str, Any] = {}
    completed: set[str] = set()
    is_a_share = is_a_share_mode(request.mode)
    stages = A_SHARE_STAGES if is_a_share else COMMON_STAGES
    stage_order = A_SHARE_STAGE_ORDER if is_a_share else COMMON_STAGE_ORDER

    yield event(
        "start",
        {
            "task": request.task,
            "symbols": request.symbols,
            "sectors": request.sectors,
            "mode": request.mode,
            "stages": ordered_stage_list(stages, stage_order),
        },
    )
    yield stage_status("information_analysis", "running", started_at)

    try:
        agent_configs = resolve_agent_configs(request)
        graph = build_a_share_auto_trade_graph(agent_configs=agent_configs) if is_a_share else build_stock_graph(agent_configs=agent_configs)
        inputs = build_graph_inputs(request, agent_configs)

        for update in graph.stream(inputs, stream_mode="updates"):
            for node, node_update in update.items():
                if not isinstance(node_update, dict):
                    continue
                state.update(node_update)

                visible_node = visible_stage_node(node, is_a_share)
                if visible_node in stages:
                    completed.add(node)
                    output_key = stages[visible_node]["output_key"]
                    content = stage_content(visible_node, node_update, state, output_key)
                    payload: dict[str, Any] = {
                        "node": visible_node,
                        "status": "done",
                        "elapsed_ms": elapsed_ms(started_at),
                        "output_key": output_key,
                        "content": content,
                        "summary": summarize_markdown(content),
                        "node_meta": stages[visible_node],
                    }
                    if visible_node == "information_analysis":
                        payload["source_trace"] = build_information_source_trace(
                            node_update
                        )
                    yield event("stage", payload)
                    yield from emit_next_statuses(node, completed, started_at, is_a_share)

                if node == "format_output":
                    yield event(
                        "complete",
                        {
                            "elapsed_ms": elapsed_ms(started_at),
                            "final_output": node_update.get("final_output", ""),
                            "state": public_state(state),
                        },
                    )
    except Exception as exc:
        yield event(
            "error",
            {
                "elapsed_ms": elapsed_ms(started_at),
                "message": str(exc),
                "hint": "检查 OPENROUTER_API_KEY、config.yaml 模型名和网络代理设置。",
            },
        )


def resolve_agent_configs(request: DecisionRequest):
    if request.mode == "mock":
        configs = {key: dict(value) for key, value in DEFAULT_AGENT_CONFIGS.items()}
        configs["information"] = {
            **configs["information"],
            "collector": {"enabled": False},
        }
        return configs

    config_path = Path(request.config_path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    return load_agent_configs(config_path)


def build_graph_inputs(
    request: DecisionRequest,
    agent_configs: dict[str, Any],
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "task": request.task,
        "candidates": parse_symbols(request.symbols),
        "agent_configs": agent_configs,
        "metadata": {"ui_mode": request.mode},
    }
    if is_a_share_mode(request.mode):
        inputs.update(
            {
                "scan_scope": {
                    "market": "A_SHARE",
                    "sectors": parse_csv(request.sectors),
                    "exclude_st": True,
                    "exclude_new_days": 60,
                },
                "portfolio_context": {
                    "current_positions": [],
                    "available_capital": request.capital,
                    "max_position_pct": 20,
                    "max_drawdown_limit": 10,
                    "risk_tolerance": request.risk_tolerance,
                },
            }
        )
    return inputs


def emit_next_statuses(node: str, completed: set[str], started_at: float, is_a_share: bool):
    if node == "information_analysis":
        if is_a_share:
            yield stage_status("a_share_context", "running", started_at)
            return
        yield stage_status("bull_debate", "running", started_at)
        yield stage_status("bear_debate", "running", started_at)
    elif is_a_share and node == "a_share_context":
        yield stage_status("bull_debate", "running", started_at)
        yield stage_status("bear_debate", "running", started_at)
    elif {"bull_debate", "bear_debate"}.issubset(completed) and "judge_decision" not in completed:
        yield stage_status("judge_decision", "running", started_at)
    elif node == "judge_decision":
        yield stage_status("risk_review", "running", started_at)
    elif is_a_share and node == "risk_review":
        yield stage_status("portfolio_manager", "running", started_at)
    elif is_a_share and node == "portfolio_manager":
        yield stage_status("save_trade_plan", "running", started_at)


def stage_status(node: str, status: str, started_at: float) -> str:
    return event(
        "stage_status",
        {
            "node": node,
            "status": status,
            "elapsed_ms": elapsed_ms(started_at),
        },
    )


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "information_workflow",
        "provider_selection",
        "signal_reasoning",
        "raw_market_data",
        "info_report",
        "bull_case",
        "bear_case",
        "judge_decision",
        "risk_report",
        "stock_pool",
        "sector_summary",
        "confidence_level",
        "data_gaps",
        "bull_cases",
        "bear_cases",
        "judge_rulings",
        "judge_report",
        "overall_market_view",
        "final_decision",
        "trade_plan",
        "alternative_scenarios",
        "manager_report",
        "manager_confidence",
        "portfolio_context",
        "final_output",
    ]
    return {key: state[key] for key in keys if key in state}


def ordered_stage_list(stages: dict[str, dict[str, str]], order: list[str]) -> list[dict[str, str]]:
    return [stages[node] for node in order if node in stages]


def is_a_share_mode(mode: str) -> bool:
    return mode in {"a_share_daily", "a_share_sector", "a_share_deep"}


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def visible_stage_node(node: str, is_a_share: bool) -> str:
    if is_a_share and node == "skip_trade_plan":
        return "save_trade_plan"
    return node


def stage_content(
    visible_node: str,
    node_update: dict[str, Any],
    state: dict[str, Any],
    output_key: str,
) -> str:
    if visible_node == "a_share_context":
        return render_a_share_context_report(node_update)
    if visible_node == "save_trade_plan":
        return render_trade_plan_report(node_update, state)
    content = node_update.get(output_key)
    if isinstance(content, str) and content:
        return content
    return render_structured_stage_report(visible_node, node_update)


def render_a_share_context_report(node_update: dict[str, Any]) -> str:
    stock_pool = list(node_update.get("stock_pool", []) or [])
    sector_summary = list(node_update.get("sector_summary", []) or [])
    data_gaps = list(node_update.get("data_gaps", []) or [])
    lines = [
        "## A 股上下文",
        "",
        f"- 股票池数量：{len(stock_pool)}",
        f"- 板块数量：{len(sector_summary)}",
        f"- 置信度：{node_update.get('confidence_level', 'N/A')}",
        "",
        "### 股票池",
        "| 股票 | 名称 | 板块 | 价格 | 信息评分 | 技术信号 |",
        "|---|---|---|---:|---:|---|",
    ]
    for stock in stock_pool[:12]:
        lines.append(
            "| {symbol} | {name} | {sector} | {price} | {score} | {signal} |".format(
                symbol=stock.get("symbol", ""),
                name=stock.get("name", ""),
                sector=stock.get("sector", ""),
                price=stock.get("price", ""),
                score=stock.get("information_score", ""),
                signal=stock.get("technical_signal", ""),
            )
        )
    if not stock_pool:
        lines.append("| 暂无 | 暂无 | 暂无 |  |  |  |")
    if data_gaps:
        lines.extend(["", "### 数据缺口", *[f"- {item}" for item in data_gaps]])
    return "\n".join(lines)


def render_trade_plan_report(node_update: dict[str, Any], state: dict[str, Any]) -> str:
    metadata = dict(node_update.get("metadata", {}) or state.get("metadata", {}) or {})
    plan = dict(state.get("trade_plan", {}) or {})
    decision = dict(state.get("final_decision", {}) or {})
    stocks = list(plan.get("monitored_stocks", []) or [])
    if not stocks:
        return "\n".join(
            [
                "## 交易计划",
                "",
                f"- 最终动作：{decision.get('action', 'WAIT')}",
                f"- 原因：{decision.get('reasoning', '未生成交易计划。')}",
                "- 状态：未写入交易计划文件",
            ]
        )
    lines = [
        "## 交易计划",
        "",
        f"- 最终动作：{decision.get('action', 'BUY')}",
        f"- 计划文件：`{metadata.get('trade_plan_file', 'data/trade_plan.json')}`",
        "",
        "| 标的 | 数量 | 仓位 | 买入触发 | 卖出触发 | 止损 | 止盈 | 有效期 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for stock in stocks:
        lines.append(
            "| {symbol} {name} | {quantity} | {allocation_pct}% | {buy} | {sell} | {stop} | {take} | {valid_from} 至 {valid_until} |".format(
                symbol=stock.get("symbol", ""),
                name=stock.get("name", ""),
                quantity=stock.get("quantity", ""),
                allocation_pct=stock.get("allocation_pct", ""),
                buy=stock.get("buy_trigger_price", ""),
                sell=stock.get("sell_trigger_price", ""),
                stop=stock.get("stop_loss_price", ""),
                take=stock.get("take_profit_price", ""),
                valid_from=stock.get("valid_from", ""),
                valid_until=stock.get("valid_until", ""),
            )
        )
    return "\n".join(lines)


def render_structured_stage_report(node: str, node_update: dict[str, Any]) -> str:
    return f"## {node}\n\n```json\n{json.dumps(node_update, ensure_ascii=False, indent=2, default=str)}\n```"


def summarize_markdown(content: str) -> str:
    text = " ".join(
        line.strip().lstrip("#-*>0123456789. ")
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("|") and not line.strip().startswith("```")
    )
    if len(text) <= 220:
        return text or "暂无摘要。"
    return text[:220].rstrip() + "..."


def build_information_source_trace(node_update: dict[str, Any]) -> list[dict[str, Any]]:
    raw_data = node_update.get("raw_market_data") or {}
    sources = dict(raw_data.get("sources", {}) or {})
    errors = dict(raw_data.get("errors", {}) or {})
    trace: list[dict[str, Any]] = []

    for label, value in sources.items():
        descriptor = describe_source(label, value)
        trace.append(
            {
                **descriptor,
                "label": label,
                "status": "success",
                "message": "接通成功",
                "detail": compact_source_detail(value),
            }
        )

    for label, error in errors.items():
        descriptor = describe_source(label)
        trace.append(
            {
                **descriptor,
                "label": label,
                "status": "failed",
                "message": "接通失败",
                "detail": str(error),
            }
        )

    return sorted(trace, key=lambda item: (item["status"] != "success", item["label"]))


def describe_source(label: str, value: Any | None = None) -> dict[str, str]:
    parts = label.split(".")
    if label.startswith("equity.") and len(parts) >= 3:
        symbol = parts[1]
        data_key = ".".join(parts[2:])
        if data_key in {"price_daily", "price_weekly"}:
            interval = "日线" if data_key == "price_daily" else "周线"
            return source_descriptor(
                "Yahoo Finance",
                "https://finance.yahoo.com/",
                f"{symbol} {interval} OHLCV 价格数据",
            )
        if data_key == "stooq_price_daily":
            return source_descriptor(
                "Stooq",
                "https://stooq.com/",
                f"{symbol} 日线价格数据",
            )
        if data_key == "options_nearest":
            return source_descriptor(
                "Yahoo Finance / yfinance",
                "https://finance.yahoo.com/options",
                f"{symbol} 最近到期期权链",
            )
        if data_key == "edgar_form4":
            return source_descriptor(
                "SEC EDGAR",
                "https://www.sec.gov/edgar",
                f"{symbol} Form 4 内部人交易",
            )
        if data_key == "tencent_metrics":
            return source_descriptor(
                "腾讯财经",
                "https://qt.gtimg.cn/",
                f"{symbol} A 股行情、估值和成交活跃度",
            )
        if data_key.startswith("mootdx"):
            return source_descriptor(
                "通达信 / MooTDX",
                "https://github.com/mootdx/mootdx",
                f"{symbol} A 股行情与财务数据",
            )

    if label.startswith("macro.price."):
        symbol = label.removeprefix("macro.price.")
        return source_descriptor(
            "Yahoo Finance",
            "https://finance.yahoo.com/",
            f"{symbol} 宏观代理价格数据",
        )
    if label == "macro.yield_curve":
        return source_descriptor(
            "U.S. Treasury",
            "https://home.treasury.gov/",
            "美国国债收益率曲线",
        )
    if label == "macro.fear_greed":
        return source_descriptor(
            "CNN Fear & Greed",
            "https://www.cnn.com/markets/fear-and-greed",
            "市场情绪指数",
        )
    if label == "macro.cme_fedwatch":
        return source_descriptor(
            "CME FedWatch",
            "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
            "联邦基金期货隐含利率概率",
        )
    if label.startswith("macro.cftc."):
        return source_descriptor(
            "CFTC",
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
            f"{label.removeprefix('macro.cftc.')} COT 持仓报告",
        )
    if label.startswith("macro.bis."):
        return source_descriptor(
            "BIS",
            "https://www.bis.org/statistics/",
            "央行利率与信用周期数据",
        )
    if label.startswith("macro.worldbank."):
        return source_descriptor(
            "World Bank",
            "https://data.worldbank.org/",
            f"{label.removeprefix('macro.worldbank.')} 宏观指标",
        )
    if label == "prediction.kalshi.markets":
        return source_descriptor(
            "Kalshi",
            "https://kalshi.com/markets",
            "预测市场合约与真实资金概率",
        )
    if label.startswith("prediction.polymarket."):
        topic = label.removeprefix("prediction.polymarket.")
        return source_descriptor(
            "Polymarket",
            "https://polymarket.com/",
            f"{topic} 事件市场概率",
        )
    if label.startswith("crypto.coingecko."):
        return source_descriptor(
            "CoinGecko",
            "https://www.coingecko.com/",
            "加密现货、市值和风险偏好数据",
        )
    if label.startswith("crypto.deribit."):
        parts = label.split(".")
        currency = parts[2] if len(parts) > 2 else "crypto"
        data_kind = "期权链" if label.endswith("option_chain") else "期货期限结构"
        return source_descriptor(
            "Deribit",
            "https://www.deribit.com/",
            f"{currency} {data_kind}",
        )
    if label.startswith("web.search."):
        query = value.get("query") if isinstance(value, dict) else ""
        data = f"网页搜索摘要：{query}" if query else "网页搜索摘要"
        return source_descriptor("DuckDuckGo / Web Search", "https://duckduckgo.com/", data)

    return source_descriptor("未知数据源", "", label)


def source_descriptor(site: str, url: str, data: str) -> dict[str, str]:
    return {"site": site, "url": url, "data": data}


def compact_source_detail(value: Any) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    if len(text) <= 220:
        return text
    return text[:220] + "..."


def elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def event(event_type: str, payload: dict[str, Any]) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
