from __future__ import annotations

from statistics import mean
from typing import Any

from agents.portfolio_manager_agent import build_portfolio_decision
from agents.trace_logger import log_agent_output, log_agent_start
from schemas.state import AgentRuntimeConfig, MarketDecisionState


class PortfolioDecisionNode:
    def __init__(self, config: AgentRuntimeConfig):
        self.config = config

    def __call__(self, state: MarketDecisionState) -> dict[str, Any]:
        log_agent_start("portfolio_decision", state)
        output = build_portfolio_decision(state, self.config)
        log_agent_output("portfolio_decision", "final_decision", output.get("final_decision", {}))
        return output


def structure_bull_cases(state: MarketDecisionState) -> dict[str, Any]:
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
                "risk_acknowledged": "数据缺口和市场波动可能导致信号失效。",
            }
        )
    return {
        "bull_cases": cases,
        "bull_summary": "多头侧重点：估值合理性、成交活跃度、技术信号和行业催化。",
        "bull_overall_confidence": round(mean(confidences) / 5, 2) if confidences else 0.0,
    }


def structure_bear_cases(state: MarketDecisionState) -> dict[str, Any]:
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


def structure_judge_rulings(state: MarketDecisionState) -> dict[str, Any]:
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
        "judge_rulings": rulings,
        "judge_report": state.get("judge_decision", ""),
        "overall_market_view": "统一链路以结构化行情和风控为先，数据缺口存在时只允许低仓位或等待。",
    }


def save_trade_plan(state: MarketDecisionState) -> dict[str, Any]:
    return {
        "metadata": {
            **dict(state.get("metadata", {}) or {}),
            "trade_plan_file": None,
            "trade_plan_persistence": "display_only",
        }
    }


def format_final_output(state: MarketDecisionState) -> dict[str, str]:
    log_agent_start("final_output", state)
    decision = state.get("final_decision", {})
    action = decision.get("action", "WAIT")
    plan_note = "\n\n仅生成交易决策展示，未写入交易计划 JSON 文件。"
    final_output = "\n".join(
        [
            "# 股票自动购买决策",
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
    log_agent_output("final_output", "final_output", final_output)
    return {"final_output": final_output}


def build_bull_catalysts(stock: dict[str, Any]) -> list[str]:
    catalysts = [
        str(stock.get("technical_signal") or "技术信号待确认"),
        str(stock.get("preliminary_reason") or "候选池入选理由"),
    ]
    if stock.get("pe_ratio"):
        catalysts.append(f"PE {stock['pe_ratio']} 处于可比较区间")
    return catalysts[:4]


def build_bear_risks(stock: dict[str, Any]) -> list[str]:
    risks = ["市场波动和交易执行风险", "资金面/财务增强字段缺口"]
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


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
