from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import mean
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from agents.bear_agent import BearAgent
from agents.bull_agent import BullAgent
from agents.information_agent import InformationCollectionAgent
from agents.judge_agent import JudgeAgent
from agents.portfolio_manager_agent import PortfolioManagerAgent
from agents.risk_agent import RiskAgent
from agents.trace_logger import log_agent_output, log_agent_start
from graph.stock_graph import DEFAULT_AGENT_CONFIGS
from schemas.a_share_state import AShareAutoPurchaseState
from schemas.state import AgentRuntimeConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRADE_PLAN_PATH = PROJECT_ROOT / "data" / "trade_plan.json"

DEFAULT_A_SHARE_AGENT_CONFIGS: dict[str, AgentRuntimeConfig] = {
    **{key: dict(value) for key, value in DEFAULT_AGENT_CONFIGS.items()},
    "portfolio_manager": {
        "name": "portfolio_manager",
        "role": "总经理 Agent",
        "model": {"provider": "mock", "model": "mock-portfolio-manager", "temperature": 0.1},
        "position_sizing": {
            "max_single_position_pct": 20,
            "max_total_exposure_pct": 80,
            "cash_reserve_min_pct": 20,
        },
        "risk_control": {
            "max_drawdown_pct": 10,
            "stop_loss_pct": 8,
            "take_profit_pct": 20,
        },
    },
}


def build_a_share_auto_trade_graph(
    *,
    agent_configs: dict[str, AgentRuntimeConfig] | None = None,
    information_agent: Any | None = None,
) -> Any:
    configs = merge_agent_configs(agent_configs)

    builder = StateGraph(AShareAutoPurchaseState)
    builder.add_node(
        "information_analysis",
        information_agent or InformationCollectionAgent(configs["information"]),
    )
    builder.add_node("a_share_context", build_a_share_context)
    builder.add_node("bull_debate", BullAgent(configs["bull"]))
    builder.add_node("bear_debate", BearAgent(configs["bear"]))
    builder.add_node("bull_cases", structure_bull_cases)
    builder.add_node("bear_cases", structure_bear_cases)
    builder.add_node("judge_decision", JudgeAgent(configs["judge"]))
    builder.add_node("judge_rulings", structure_judge_rulings)
    builder.add_node("risk_review", AShareRiskReview(configs["risk"]))
    builder.add_node("portfolio_manager", PortfolioManagerAgent(configs["portfolio_manager"]))
    builder.add_node("save_trade_plan", save_trade_plan)
    builder.add_node("skip_trade_plan", skip_trade_plan)
    builder.add_node("format_output", format_a_share_output)

    builder.add_edge(START, "information_analysis")
    builder.add_edge("information_analysis", "a_share_context")
    builder.add_edge("a_share_context", "bull_debate")
    builder.add_edge("a_share_context", "bear_debate")
    builder.add_edge("bull_debate", "bull_cases")
    builder.add_edge("bear_debate", "bear_cases")
    builder.add_edge(["bull_cases", "bear_cases"], "judge_decision")
    builder.add_edge("judge_decision", "judge_rulings")
    builder.add_edge("judge_rulings", "risk_review")
    builder.add_edge("risk_review", "portfolio_manager")
    builder.add_conditional_edges(
        "portfolio_manager",
        final_action,
        {"save_plan": "save_trade_plan", "no_plan": "skip_trade_plan"},
    )
    builder.add_edge("save_trade_plan", "format_output")
    builder.add_edge("skip_trade_plan", "format_output")
    builder.add_edge("format_output", END)

    return builder.compile()


class AShareRiskReview:
    def __init__(self, config: AgentRuntimeConfig):
        self.agent = RiskAgent(config)

    def __call__(self, state: AShareAutoPurchaseState) -> dict[str, Any]:
        return {
            **self.agent(state),
            **carry_a_share_context(state),
        }


def carry_a_share_context(state: AShareAutoPurchaseState) -> dict[str, Any]:
    keys = (
        "stock_pool",
        "sector_summary",
        "confidence_level",
        "data_gaps",
        "bull_cases",
        "bear_cases",
        "bull_summary",
        "bear_summary",
        "judge_rulings",
        "judge_report",
        "overall_market_view",
        "portfolio_context",
        "macro_context",
    )
    return {key: state[key] for key in keys if key in state}


def merge_agent_configs(
    agent_configs: dict[str, AgentRuntimeConfig] | None,
) -> dict[str, AgentRuntimeConfig]:
    configs = {key: dict(value) for key, value in DEFAULT_A_SHARE_AGENT_CONFIGS.items()}
    for name, override in (agent_configs or {}).items():
        base = dict(configs.get(name, {"name": name, "role": name}))
        base.update(override)
        if "model" in override and isinstance(override["model"], dict):
            model = dict(configs.get(name, {}).get("model", {}))
            model.update(override["model"])
            base["model"] = model
        configs[name] = base
    return configs


def build_a_share_context(state: AShareAutoPurchaseState) -> dict[str, Any]:
    log_agent_start("a_share_context", state)
    raw_data = dict(state.get("raw_market_data", {}) or {})
    sources = dict(raw_data.get("sources", {}) or {})
    metrics_by_symbol = extract_tencent_metrics(sources)
    stock_pool = build_stock_pool(state, metrics_by_symbol)
    sector_summary = build_sector_summary(stock_pool)
    data_gaps = infer_data_gaps(raw_data, stock_pool, sector_summary)
    confidence = infer_confidence(raw_data, stock_pool, data_gaps)
    macro_context = extract_macro_context(sources)

    output = {
        "stock_pool": stock_pool,
        "sector_summary": sector_summary,
        "confidence_level": confidence,
        "data_gaps": data_gaps,
        "macro_context": macro_context,
        "metadata": {
            **dict(state.get("metadata", {}) or {}),
            "a_share_context": {
                "stock_pool_size": len(stock_pool),
                "sector_count": len(sector_summary),
                "confidence_level": confidence,
            },
        },
    }
    log_agent_output("a_share_context", "stock_pool", stock_pool)
    return output


def build_stock_pool(
    state: AShareAutoPurchaseState,
    metrics_by_symbol: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = list(state.get("candidates", []) or [])
    stock_pool: list[dict[str, Any]] = []
    for candidate in candidates:
        symbol = normalize_a_share_symbol(str(candidate.get("symbol", "")))
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
                "sector": merged.get("sector") or "未分类板块",
                "price": price,
                "pe_ratio": to_float(merged.get("pe")),
                "pb_ratio": to_float(merged.get("pb")),
                "roe": to_float(merged.get("roe")),
                "revenue_growth_yoy": to_float(merged.get("revenue_growth_yoy")),
                "net_profit_growth_yoy": to_float(merged.get("net_profit_growth_yoy")),
                "market_cap_yi": to_float(merged.get("total_market_cap_cny_100m")),
                "turnover_rate": to_float(merged.get("turnover_rate")),
                "north_net_flow_5d": to_float(merged.get("north_net_flow_5d")),
                "technical_signal": infer_technical_signal(merged),
                "information_score": score,
                "preliminary_reason": candidate.get("reason") or "候选标的来自 A 股筛选流程。",
            }
        )
    return sorted(stock_pool, key=lambda item: item.get("information_score") or 0, reverse=True)


def extract_tencent_metrics(sources: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for label, value in sources.items():
        if not label.endswith(".tencent_metrics") or not isinstance(value, dict):
            continue
        for item in value.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            symbol = normalize_a_share_symbol(str(item.get("symbol") or label.split(".")[1]))
            if symbol:
                metrics[symbol] = item
    return metrics


def build_sector_summary(stock_pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sectors: dict[str, list[dict[str, Any]]] = {}
    for stock in stock_pool:
        sectors.setdefault(str(stock.get("sector") or "未分类板块"), []).append(stock)

    summary = []
    for sector_name, rows in sectors.items():
        changes = [to_float(row.get("change_pct_5d")) for row in rows]
        pe_values = [to_float(row.get("pe_ratio")) for row in rows]
        turnover_values = [to_float(row.get("turnover_rate")) for row in rows]
        avg_turnover = average([item for item in turnover_values if item is not None])
        summary.append(
            {
                "sector_name": sector_name,
                "change_pct_5d": average([item for item in changes if item is not None]),
                "change_pct_20d": None,
                "avg_pe": average([item for item in pe_values if item is not None]),
                "money_flow_signal": infer_money_flow_signal(avg_turnover),
                "policy_catalyst": "未接入政策事件结构化数据",
            }
        )
    return summary


def infer_data_gaps(
    raw_data: dict[str, Any],
    stock_pool: list[dict[str, Any]],
    sector_summary: list[dict[str, Any]],
) -> list[str]:
    gaps: list[str] = []
    errors = dict(raw_data.get("errors", {}) or {})
    if errors:
        gaps.append(f"{len(errors)} 个数据源采集失败，需降低置信度。")
    if not stock_pool:
        gaps.append("未形成 A 股股票池。")
    if not sector_summary or any(item.get("sector_name") == "未分类板块" for item in sector_summary):
        gaps.append("板块指数/申万行业分类 Provider 尚未接入。")
    if any(stock.get("north_net_flow_5d") is None for stock in stock_pool):
        gaps.append("北向资金 5 日净流入数据尚未接入。")
    if any(stock.get("roe") is None for stock in stock_pool):
        gaps.append("ROE、营收增速、净利润增速等财务增强字段不足。")
    return gaps


def infer_confidence(
    raw_data: dict[str, Any],
    stock_pool: list[dict[str, Any]],
    data_gaps: list[str],
) -> float:
    source_count = int(raw_data.get("source_count") or 0)
    error_count = int(raw_data.get("error_count") or 0)
    score = 0.35
    if stock_pool:
        score += 0.25
    if source_count:
        score += min(source_count / 20, 0.25)
    if error_count:
        score -= min(error_count / 20, 0.2)
    score -= min(len(data_gaps) * 0.04, 0.2)
    return round(max(min(score, 0.9), 0.1), 2)


def extract_macro_context(sources: dict[str, Any]) -> dict[str, Any]:
    return {
        label: value
        for label, value in sources.items()
        if label.startswith("macro.") or label.startswith("prediction.") or label.startswith("crypto.")
    }


def structure_bull_cases(state: AShareAutoPurchaseState) -> dict[str, Any]:
    stock_pool = list(state.get("stock_pool", []) or [])
    bull_case = state.get("bull_case", "")
    cases = []
    confidences = []
    for stock in stock_pool:
        price = to_float(stock.get("price"))
        score = to_float(stock.get("information_score")) or 0
        confidence = confidence_from_score(score)
        confidences.append(confidence)
        cases.append(
            {
                "symbol": stock.get("symbol"),
                "name": stock.get("name", ""),
                "bull_argument": bull_case,
                "key_catalysts": build_bull_catalysts(stock),
                "target_price": round(price * 1.12, 2) if price else None,
                "buy_trigger_price": round(price * 0.99, 2) if price else None,
                "upside_pct": 12.0 if price else None,
                "confidence": confidence,
                "time_horizon": "1-3个月",
                "risk_acknowledged": "数据缺口和 A 股波动可能导致信号失效。",
            }
        )
    return {
        "bull_cases": cases,
        "bull_summary": "多头侧重点：估值合理性、成交活跃度、技术信号和行业催化。",
        "bull_overall_confidence": round(mean(confidences) / 5, 2) if confidences else 0.0,
    }


def structure_bear_cases(state: AShareAutoPurchaseState) -> dict[str, Any]:
    stock_pool = list(state.get("stock_pool", []) or [])
    bear_case = state.get("bear_case", "")
    cases = []
    confidences = []
    for stock in stock_pool:
        price = to_float(stock.get("price"))
        score = to_float(stock.get("information_score")) or 0
        confidence = max(1, 6 - confidence_from_score(score))
        confidences.append(confidence)
        cases.append(
            {
                "symbol": stock.get("symbol"),
                "name": stock.get("name", ""),
                "bear_argument": bear_case,
                "key_risks": build_bear_risks(stock),
                "downside_price": round(price * 0.92, 2) if price else None,
                "sell_trigger_price": round(price * 0.95, 2) if price else None,
                "downside_pct": 8.0 if price else None,
                "confidence": confidence,
                "time_horizon": "1-3个月",
            }
        )
    return {
        "bear_cases": cases,
        "bear_summary": "空头侧重点：估值偏高、财务缺口、资金面缺口和技术破位。",
        "bear_overall_confidence": round(mean(confidences) / 5, 2) if confidences else 0.0,
    }


def structure_judge_rulings(state: AShareAutoPurchaseState) -> dict[str, Any]:
    stock_pool = list(state.get("stock_pool", []) or [])
    data_quality = round(float(state.get("confidence_level") or 0) * 100, 2)
    rulings = []
    for stock in stock_pool:
        score = float(stock.get("information_score") or 0)
        ruling = infer_ruling(score, data_quality, stock.get("price"))
        bull_score = min(score + 8, 100)
        bear_score = max(100 - score, 0)
        rulings.append(
            {
                "symbol": stock.get("symbol"),
                "name": stock.get("name", ""),
                "ruling": ruling,
                "reasoning": (
                    f"信息评分 {score:.1f}，数据质量 {data_quality:.1f}；"
                    "结合多空论据后给出价格触发式结论。"
                ),
                "bull_score": round(bull_score, 2),
                "bear_score": round(bear_score, 2),
                "data_quality": data_quality,
                "credibility_level": infer_credibility(data_quality),
                "final_recommendation": final_recommendation_for_ruling(ruling),
            }
        )
    return {
        **carry_a_share_context(state),
        "judge_rulings": rulings,
        "judge_report": state.get("judge_decision", ""),
        "overall_market_view": "A 股链路以结构化行情和风控为先，数据缺口存在时只允许低仓位或等待。",
    }


def final_action(state: AShareAutoPurchaseState) -> Literal["save_plan", "no_plan"]:
    action = state.get("final_decision", {}).get("action", "WAIT")
    return "save_plan" if action == "BUY" else "no_plan"


def save_trade_plan(state: AShareAutoPurchaseState) -> dict[str, Any]:
    plan = dict(state.get("trade_plan", {}) or {})
    TRADE_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRADE_PLAN_PATH.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "metadata": {
            **dict(state.get("metadata", {}) or {}),
            "trade_plan_file": str(TRADE_PLAN_PATH),
        }
    }


def skip_trade_plan(state: AShareAutoPurchaseState) -> dict[str, Any]:
    return {
        "metadata": {
            **dict(state.get("metadata", {}) or {}),
            "trade_plan_file": None,
        }
    }


def format_a_share_output(state: AShareAutoPurchaseState) -> dict[str, str]:
    log_agent_start("format_a_share_output", state)
    decision = state.get("final_decision", {})
    action = decision.get("action", "WAIT")
    plan_file = dict(state.get("metadata", {}) or {}).get("trade_plan_file")
    plan_note = f"\n\n交易计划文件：`{plan_file}`" if plan_file else "\n\n未生成交易计划文件。"
    final_output = "\n".join(
        [
            "# A 股自动购买决策",
            "",
            f"- 最终动作：{action}",
            f"- 决策理由：{decision.get('reasoning', '暂无')}",
            f"- 总经理置信度：{state.get('manager_confidence', 'N/A')}",
            "",
            "## 总经理报告",
            "",
            state.get("manager_report", "暂无总经理报告。"),
            plan_note,
            "",
            "> 本系统为实验性研究项目，不构成任何投资建议。",
        ]
    )
    log_agent_output("format_a_share_output", "final_output", final_output)
    return {"final_output": final_output}


def normalized_information_score(candidate_score: Any, metrics: dict[str, Any]) -> float:
    score = to_float(candidate_score)
    if score is None:
        score = 50.0
    elif score <= 10:
        score = score * 12

    pe = to_float(metrics.get("pe"))
    pb = to_float(metrics.get("pb"))
    if pe and pe > 100:
        score -= 8
    if pb and pb > 15:
        score -= 5
    return round(max(min(score, 100), 0), 2)


def infer_technical_signal(metrics: dict[str, Any]) -> str:
    change_pct = to_float(metrics.get("change_pct"))
    volume_ratio = to_float(metrics.get("volume_ratio"))
    if change_pct is not None and volume_ratio is not None:
        if change_pct > 0 and volume_ratio >= 1.2:
            return "放量上涨"
        if change_pct < 0 and volume_ratio >= 1.2:
            return "放量下跌"
        if change_pct > 0:
            return "价格转强"
    return "待补充均线/MACD/KDJ"


def infer_money_flow_signal(avg_turnover: float | None) -> str:
    if avg_turnover is None:
        return "资金面数据不足"
    if avg_turnover >= 5:
        return "成交活跃"
    if avg_turnover >= 2:
        return "成交温和"
    return "成交偏弱"


def build_bull_catalysts(stock: dict[str, Any]) -> list[str]:
    catalysts = [
        str(stock.get("technical_signal") or "技术信号待确认"),
        str(stock.get("preliminary_reason") or "候选池入选理由"),
    ]
    if stock.get("pe_ratio"):
        catalysts.append(f"PE {stock['pe_ratio']} 处于可比较区间")
    return catalysts[:4]


def build_bear_risks(stock: dict[str, Any]) -> list[str]:
    risks = ["A 股波动和 T+1 交易限制", "北向资金/融资融券数据缺口"]
    pe = to_float(stock.get("pe_ratio"))
    if pe and pe > 80:
        risks.append("PE 偏高")
    if stock.get("roe") is None:
        risks.append("ROE 等财务质量字段缺失")
    return risks


def confidence_from_score(score: float) -> int:
    if score >= 85:
        return 5
    if score >= 70:
        return 4
    if score >= 55:
        return 3
    if score >= 40:
        return 2
    return 1


def infer_ruling(score: float, data_quality: float, price: Any) -> str:
    if price is None or data_quality < 35:
        return "WATCH"
    if score >= 85 and data_quality >= 65:
        return "STRONG_BUY"
    if score >= 70 and data_quality >= 50:
        return "BUY"
    if score >= 45:
        return "WATCH"
    if score >= 30:
        return "AVOID"
    return "STRONG_AVOID"


def infer_credibility(data_quality: float) -> str:
    if data_quality >= 70:
        return "HIGH"
    if data_quality >= 45:
        return "MEDIUM"
    return "LOW"


def final_recommendation_for_ruling(ruling: str) -> str:
    if ruling in {"STRONG_BUY", "BUY"}:
        return "仅按价格触发条件和风控仓位执行。"
    if ruling == "WATCH":
        return "保持观察，等待数据和价格信号确认。"
    return "不进入自动购买计划。"


def normalize_a_share_symbol(symbol: str) -> str:
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


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)
